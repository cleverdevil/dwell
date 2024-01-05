'''
Micropub Blueprint for Dwell.

This module contains all endpoints for Dwell's Micropub implementation,
which aims to completly comply with the Micropub specification, including
CRUD operations, syndication, and media endpoint.
'''

import json
import pathlib
import urllib.parse
import uuid

import arrow
import flask
import hashfs
import slugify

import conf

from .. import model
from . import indieauth

# instantiate the blueprint for the micropub endpoint
blueprint = flask.Blueprint(
    'micropub',
    __name__,
    template_folder=pathlib.Path('templates').absolute()
)

# create a hashfs media storage directory
media_store = hashfs.HashFS(
    'static/media',
    depth=3,
    width=2,
    algorithm='sha256'
)


@blueprint.route('/micropub', methods=['GET'])
def micropub_get():
    '''
    HTTP GET /micropub

    This request provides a query interface for the micropub endpoint,
    including metadata about the media endpoint, syndication options,
    and fetching raw JSON representations of content.
    '''

    if flask.request.args.get('q') == 'config':
        return {'media-endpoint': '/micropub/media'}

    # TODO: syndication configuration and response
    if flask.request.args.get('q') == 'syndicate-to':
        return {'syndicate-to': []}

    if flask.request.args.get('q') == 'source':
        if flask.request.args.get('url'):
            url = urllib.parse.urlparse(flask.request.args.get('url'))
            post = None
            if url.path.startswith('/view'):
                uuid = url.path.split('/')[-1]
                post = model.Post.get(uuid=uuid)
            else:
                post = model.Post.get(slug=url.path)

        return post.json if post else None


@indieauth.require_auth
@blueprint.route('/micropub', methods=['POST'])
def micropub_post():
    '''
    HTTP POST /micropub

    Handle all Micropub actions, including:

    * create
    * update
    * delete
    * undelete
    '''

    # first, get our JSON payload and response object set up
    payload = {}
    response = flask.Response()
    now = arrow.get()

    # determine content type
    content_type = flask.request.headers['Content-Type']

    # in the event that the POST data is urlencoded form data...
    if content_type.startswith('application/x-www-form-urlencoded'):
        # if an action is specified, that means we don't need to decode any
        # MF2 data, and can just use the passed-in parameters
        if flask.request.args.get('action'):
            payload = flask.request.args

        # otherwise, decode the data into a standard MF2 JSON structure
        else:
            payload = decode_mf2(flask.request.args)

    # if its a multipart request, make sure to handle that properly
    elif content_type.startswith('multipart/form-data'):
        # multipart means that one of the bits is a media upload
        payload = decode_mf2(flask.request.form, media_upload=True)

    # hey, its JSON data, which means we have MF2 data we can validate later
    elif content_type.startswith('application/json'):
        payload = flask.request.json

    # if all of these conditions fail, reject the request
    else:
        flask.abort(400, 'Invalid request data')

    # handle update, delete, and undelete actions
    if payload.get('action') == 'update':
        indieauth.enforce_authorized_scope('update')
        if update_post(payload):
            response.status_code = 204
            return response

        flask.abort(400, 'Invalid request data')
    elif payload.get('action') == 'delete':
        indieauth.enforce_authorized_scope('delete')
        if delete_post(payload):
            response.status_code = 204
            return response

        flask.abort(400, 'Invalid request data')
    elif payload.get('action') == 'undelete':
        indieauth.enforce_authorized_scope('undelete')
        if undelete_post(payload):
            response.status_code = 204
            return response

        flask.abort(400, 'Invalid request data')

    # handle create requests... first, if there is no publish date,
    # synthesize one
    indieauth.enforce_authorized_scope('create')
    if 'published' not in payload['properties']:
        payload['properties']['published'] = [now.isoformat()]

    # if an author property hasn't been provided, synthesize one
    if 'author' not in payload['properties']:
        payload['properties']['author'] = [
            {
                'type': ['h-card'],
                'properties': {
                    'name': [conf.author.name],
                    'url': [conf.author.url],
                    'photo': [conf.author.photo]
                }
            }
        ]

    # synthesize a children record if its not present
    if 'children' not in payload:
        payload['children'] = []

    # generate a slug for this post
    generate_slug_and_uuid(payload)

    # store the raw content on disk
    content = json.dumps(payload, indent=2)
    content_path = pathlib.Path(
        f'content/year={now.year}/month={now.month:02}/day={now.day:02}'
    )
    content_path.mkdir(exist_ok=True, parents=True)
    content_path = content_path / f'{payload["properties"]["post-id"][0]}.json'

    with open(content_path, 'w') as f:
        f.write(content)

    # attempt to add the record to the database without a full scan
    # and if the attempt fails, reinitialize the database
    try:
        print('Adding new post to database: ', content_path)
        model.database.add(content_path)
    except Exception:
        print('Failed to add content. Reinitializing database.')
        model.database.reinitialize()

    # redirect to the rendered content
    response.status_code = 202
    response.headers['Location'] = payload['properties']['url'][0]

    return response


@blueprint.route('/micropub/media', methods=['POST'])
@indieauth.require_auth
def media_upload():
    '''
    HTTP POST /micropub/media

    Enables authorized clients to upload media files.
    '''

    if 'file' not in flask.request.files:
        flask.abort(400, 'Invalid request: no files uploaded.')

    file = flask.request.files['file']

    if file.filename == '':
        flask.abort(400, 'Invalid request: no files uploaded.')

    permalink = upload_media(file)

    response = flask.Response()
    response.status_code = 201
    response.headers['Location'] = permalink
    return response


def upload_media(file):
    '''
    Store the provided file in the media store and return a permalink to
    the content itself.
    '''

    media = media_store.put(file.stream)
    return f'/media/{media.relpath}'


def decode_mf2(post, media_upload=False):
    '''
    The client has provided formencoded data, like an animal.
    Decode it into standard MF2 JSON.
    '''

    mf2 = {}
    mf2['type'] = ['h-' + post.get('h', 'entry')]
    mf2['properties'] = {}
    mf2['properties']['content'] = [post.get('content', '')]

    for key in post.keys():
        if key in ('h', 'content', 'access_token'):
            continue

        mf2['properties'][key.replace('[]', '')] = post.getlist(key)

    # handle multipart uploads
    for key, file in flask.request.files.items():
        if not media_upload:
            continue

        permalink = upload_media(file)
        mf2['properties'].setdefault(key.replace('[]', ''), []).append(
            permalink
        )

    return mf2


def update_post(payload):
    '''
    Update the specified post with the provided content. Support
    is included to 'replace', 'add', and 'delete' operations.
    '''

    # find the post by its URL
    if 'url' not in payload:
        return False

    url = payload['url']
    if url.startswith('http'):
        url = urllib.parse.urlparse(url).path

    post = model.Post.get(slug=url)
    updated = post.json

    for key, value in payload.get('replace', {}).items():
        updated['properties'][key] = value

    for key, value in payload.get('add', {}).items():
        target = updated['properties'].get(key, [])
        target.extend(value)
        updated['properties'][key] = target

    delete = payload.get('delete')
    if isinstance(delete, list):
        for item in delete:
            del updated['properties'][item]
    elif isinstance(delete, dict):
        for key, value in delete.items():
            target = updated['properties'].get(key, [])
            for remove in value:
                if remove in target:
                    target.remove(remove)

    content = json.dumps(updated, indent=2)
    with open(post.filename, 'w') as f:
        f.write(content)

    model.database.reinitialize()

    return True


def delete_post(payload):
    '''
    Soft delete a post by attaching a 'deleted' property into its
    MF2 JSON representation.
    '''

    payload['replace'] = {'deleted': [True]}
    return update_post(payload)


def undelete_post(payload):
    '''
    Remove the soft delete property from a post's MF2 JSON representation.
    '''

    payload['delete'] = ['deleted']
    return update_post(payload)


def generate_slug_and_uuid(mf2):
    '''
    Given the provided MF2 JSON data, create a new slug and post identifier,
    and write them to the MF2 JSON dictionary.
    '''

    seed = None

    props = mf2.get('properties', {})
    if 'name' in props:
        seed = props['name'][0]
    elif 'content' in props:
        if len(props['content']):
            for content in props['content']:
                if isinstance(content, dict):
                    if 'value' in content:
                        seed = content['value']
                    elif 'html' in content:
                        seed = content['html']
                elif isinstance(content, str):
                    seed = content

    if not seed:
        if 'like-of' in props:
            seed = 'like of ' + props['like-of'][0]
        elif 'bookmark-of' in props:
            seed = 'bookmark of ' + props['bookmark-of'][0]
        elif 'repost-of' in props:
            seed = 'repost-of ' + props['repost-of'][0]
        else:
            seed = str(uuid.uuid4())

    slug = slugify.slugify(seed, max_length=40)

    unique = False
    count = 0
    while unique is False:
        post = model.Post.get(year=arrow.get().year, slug=slug)
        if post is None:
            unique = True
        else:
            count += 1
            slug = f'{slug}-{count}'

    url = f'/{arrow.get().year}/{slug}'
    props['url'] = [url]
    props['post-id'] = [uuid.uuid4().hex]
