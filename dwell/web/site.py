'''
Flask Blueprint implementing all features of the Dwell website. For now, this
Blueprint and its supporting templates are very much designed specifically for
my own website, https://cleverdevil.io, though I may generalize it for others
to use if there is sufficient demand from willing collaborators.
'''

import json
import pathlib
import urllib

import arrow
import flask

import conf  # noqa

from .. import model

blueprint = flask.Blueprint(
    'site',
    __name__,
    template_folder=pathlib.Path('templates').absolute()
)


@blueprint.route('/<int:year>/<slug>', defaults={'content_type': 'html'})
@blueprint.route('/<int:year>/<slug>.<content_type>')
def view(year, slug, content_type):
    '''
    HTTP GET /<year>/<slug>.<content_type>

    Render the post requested by the specified slug in the specified
    content type, either html or json. If no content type is provided,
    HTML is assumed. If the post cannot be found, abort with a 404.
    '''

    slug = urllib.parse.quote(slug)
    post = model.Post.get(year=year, slug=slug)

    if not post:
        flask.abort(404)

    return flask.render_template('post.html', post=post, detail=True)


@blueprint.route('/view/<uuid>', defaults={'content_type': 'html'})
@blueprint.route('/view/<uuid>.<content_type>')
def view_by_id(uuid, content_type):
    '''
    HTTP GET /<year>/<slug>.<content_type>

    Render the post requested by the specified post uuid in the specified
    content type, either html or json. If no content type is provided,
    HTML is assumed. If the post cannot be found, abort with a 404.
    '''

    post = model.Post.get(uuid=uuid)
    return flask.render_template('post.html', post=post, detail=True)


@blueprint.route('/', defaults={'content_type': 'html'})
def home(content_type):
    '''
    HTTP GET /

    Render the homepage with its default content kinds.

    This endpoint supports pagination using `limit` and `offset` parameters.
    '''

    return content('default', content_type)


@blueprint.route('/photos')
def photos():
    '''
    HTTP GET /photos

    Render the photos page, which displays the most recent photos from photo
    posts in reverse chronological order.

    This endpoint supports pagination using `limit` and `offset` parameters.
    '''

    limit = int(flask.request.args.get('limit', 30))
    offset = int(flask.request.args.get('offset', 0))

    photos = model.Photo.query(limit=limit, offset=offset)
    count = model.Photo.query(count=True)

    return flask.render_template(
        'photos.html',
        photos=photos,
        limit=limit,
        offset=offset,
        count=count
    )


@blueprint.route('/overview')
def overview():
    '''
    HTTP GET /overview

    Render the "overview" page, which gives a single view
    of the most recent posts across all post kinds. This is
    a sort of alternative "home" page.
    '''

    kwargs = dict(
        photos=model.Photo.query(limit=40),
        interactions=model.Bookmark.query(limit=20),
        watches=model.Watch.query(limit=20),
        listens=model.Listen.query(limit=20),
        checkins=model.Checkin.query(limit=20),
        statuses=model.Status.query(limit=75),
        blogs=model.Post.query(limit=30, kinds=[
            'entry', 'review', 'recipe'
        ])
    )

    return flask.render_template('overview.html', **kwargs)


@blueprint.route('/archive')
def archive():
    '''
    HTTP GET /archive

    Render the archive index, which displays a complete set of all
    years, months, and days of content posted in the history of the
    site.
    '''

    result = model.database.connection.sql(' '.join([
        "select distinct date_trunc('day', published) d",
        "from content order by d desc"
    ])).fetchall()

    years = []
    current_year = 0
    for [date] in result:
        if date.year == 1900:
            continue

        if date.year != current_year:
            current_year = date.year
            year = {'year': date.year, 'months': []}
            for month in range(1, 13):
                year['months'].append({
                    'month': month,
                    'name': arrow.get(2000, month, 1).format('MMM'),
                    'days': []
                })
            years.append(year)

        years[-1]['months'][date.month - 1]['days'].insert(0, date.day)

    return flask.render_template(
        'archive/index.html',
        years=years
    )


@blueprint.route('/archive/<int:year>/<int:month>')
def archive_month(year, month):
    '''
    HTTP GET /archive/<year>/<month>

    Render a summary rollup of all content posted in the specified month in
    history.
    '''

    results = model.Post.query(year=year, month=month)

    posts = {}
    count = 0
    for post in results:
        count += 1
        posts.setdefault(post.kind, []).append(post)

    return flask.render_template(
        'archive/month.html',
        posts=posts,
        post_count=count,
        year=year,
        month_name=arrow.get(2000, month, 1).format('MMMM'),
        month=month
    )


@blueprint.route('/archive/<int:year>/<int:month>/<int:day>')
def archive_day(year, month, day):
    '''
    HTTP GET /archive/<year>/<month>/<day>

    Render a feed of all content published on a specific day in the history of
    the site.
    '''

    posts = model.Post.query(year=year, month=month, day=day)

    return flask.render_template(
        'archive/day.html',
        posts=posts,
        year=year,
        month=month,
        day=day
    )


@blueprint.route('/about')
def about():
    '''
    HTTP GET /about

    Render the "about me" page.
    '''

    return flask.render_template('about.html')


@blueprint.route('/now')
def now():
    '''
    HTTP GET /now

    Render a page that gives the details of my current location and location
    metadata information, overlaid on top of a nice map. Note: this endpoint
    expects a `current.json` payload file in the root directory of the project
    containing location metadata from Overland.
    '''

    with open('current.json') as f:
        current = json.loads(f.read())
        return flask.render_template('now.html', current=current)


@blueprint.route('/content/<kind>', defaults={'content_type': 'html'})
@blueprint.route('/content/<kind>.<content_type>')
def content(kind, content_type):
    '''
    HTTP GET /content/<kind>.<content_type>

    Render a content feed for the specified kind of content. The kind
    specified can also be one of the kind aliases, for backward compatability
    with Known sites that migrate to Dwell. A content type can optionally
    be specified if the user wants a JSON MF2 h-feed. The default content type
    is html.

    This endpoint supports pagination using `limit` and `offset` parameters.
    '''

    limit = int(flask.request.args.get('limit', 20))
    offset = int(flask.request.args.get('offset', 0))

    kinds = model.get_kinds_for_alias(kind)

    count = model.Post.query(
        count=True,
        kinds=[kind.__kind__.capitalize() for kind in kinds]
    )

    posts = model.Post.query(
        kinds=[kind.__kind__.capitalize() for kind in kinds],
        limit=limit,
        offset=offset
    )

    if content_type == 'json':
        return {
            'type': ['h-feed'],
            'children': [
                post.json for post in posts
            ]
        }

    flask.g.show_filters = True

    return flask.render_template(
        'feed.html',
        posts=posts,
        limit=limit,
        offset=offset,
        count=count
    )


@blueprint.route('/on-this-day/<int:month>/<int:day>')
def on_this_day(month, day):
    '''
    HTTP GET /on-this-day/<month>/<day>

    Render a feed of all content posted on a specified month and day
    over all years of content on the site.
    '''

    posts = model.Post.query(month=month, day=day)
    date = arrow.get(year=2000, month=month, day=day).format('MMMM Do')
    return flask.render_template(
        'on-this-day.html',
        posts=posts,
        date=date,
        month=month,
        day=day
    )


@blueprint.route('/on-this-day/')
def on_this_day_today():
    '''
    HTTP GET /on-this-day

    Render a feed of all content posted in history on the current
    month and day across all years of content on the site.
    '''

    today = arrow.get()
    return on_this_day(today.month, today.day)
