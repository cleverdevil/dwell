import pathlib

import flask

from dwell import model

blueprint = flask.Blueprint(
    "admin", __name__, template_folder=pathlib.Path("templates").absolute()
)


@blueprint.route("/admin")
def index():
    """
    HTTP GET /admin

    Landing page for the site administrator, allowing them to post multiple "kinds" of
    content using an intuitive form-based interface that communicates with the Dwell
    backend using Micropub.
    """

    return flask.render_template("admin/index.html", model=model)
