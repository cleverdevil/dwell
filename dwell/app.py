'''
Dwell HTTP endpoints. Includes three Flask Blueprints:

    - Site: features of the website itself, including home
      stream, pagination, on this day, now, about, and other
      site-specific features.

    - IndieAuth: implements the IndieAuth standard.

    - Micropub: implements the Micropub standard.

Future work will include Webmentions.
'''

import math
import pathlib
import uuid

import arrow
import flask

from .. import conf  # noqa

from . import model  # noqa
from .web import indieauth, micropub, site

app = flask.Flask(
    __name__,
    root_path=model.__file__.rsplit('/', 1)[0],
    static_url_path='',
    static_folder=pathlib.Path('static').absolute(),
    template_folder=pathlib.Path('templates').absolute()
)
app.register_blueprint(site.blueprint)
app.register_blueprint(indieauth.blueprint)
app.register_blueprint(micropub.blueprint)


@app.before_request
def set_shared_context():
    '''
    Jinja templates get a very small set of context in their
    namespace. Attach some useful references to make templating
    easier to deal with.
    '''

    flask.g.model = model
    flask.g.arrow = arrow
    flask.g.uuid = uuid
    flask.g.path = flask.request.path
    flask.g.math = math
    flask.g.float = float
    flask.g.int = int
    flask.g.min = min
    flask.g.max = max
    flask.g.len = len


@app.route('/admin/reload_data')
@indieauth.require_auth
def reload_data():
    '''
    HTTP GET /admin/reload_data

    Forces a recreation of the DuckDB content database from
    disk by scanning the JSON content directory structure.
    '''

    result = model.database.reinitialize()
    return dict(result=result)
