import pathlib

import flask
import flask_login

from dwell import model
from dwell.web import indieauth

login_manager = flask_login.LoginManager()


class AdminBlueprint(flask.Blueprint):
    def register(self, app, options):
        login_manager.init_app(app)
        return super().register(app, options)


blueprint = AdminBlueprint(
    "admin", __name__, template_folder=pathlib.Path("templates").absolute()
)


class User(flask_login.UserMixin):
    def __init__(self, me):
        self.me = indieauth.normalize_me(me)

    def get_id(self):
        return self.me

    @classmethod
    def get(self, me):
        return User(me)


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@login_manager.unauthorized_handler
def unauthorized_handler():
    return flask.redirect("/login")


@blueprint.route("/admin")
@flask_login.login_required
def index():
    """
    HTTP GET /admin

    Landing page for the site administrator, allowing them to post multiple "kinds" of
    content using an intuitive form-based interface that communicates with the Dwell
    backend using Micropub.
    """

    return flask.render_template("admin/index.html", model=model)


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    if flask.request.method == "POST":
        me = flask.request.form.get("me")
        password = flask.request.form.get("password")
        remember = True if flask.request.form.get("remember") else False

        if indieauth.verify_password(me, password):
            flask_login.login_user(flask.current_app.User.get(me), remember=remember)
            return flask.redirect(flask.url_for("admin.index"))

        flask.flash("Invalid credentials. Try again.")
        return flask.redirect(flask.url_for("admin.login"))
    else:
        return flask.render_template("admin/login.html")


@blueprint.route("/logout")
def logout():
    flask_login.logout_user()
    return flask.redirect("/")
