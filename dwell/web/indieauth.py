"""
Flask Blueprint that provides an implementation of the IndieAuth standard.
It attempts to be a complete implementation with convenient decorators to
secure endpoints.
"""

import datetime
import hashlib
import pathlib
import uuid
from urllib.parse import urlencode

import arrow
import duckdb
import flask
import jwt

from ... import conf

blueprint = flask.Blueprint(
    "indieauth", __name__, template_folder=pathlib.Path("templates").absolute()
)


# create a DuckDB database for tokens/codes
authdb = duckdb.connect("indieauth.db")
authdb.sql(
    """create table if not exists codes (
    code varchar,
    client_id varchar,
    redirect_url varchar,
    created timestamp,
    expires timestamp,
    me varchar,
    scope varchar
)"""
)


def require_auth(func):
    """
    This decorator secures endpoints, requiring a valid authorization
    code from the IndieAuth endpoint. Note: this does not check scopes,
    which should be verified by the decorated endpoint method using the
    list of scopes provided in `flask.request.authorized_scopes`.
    """

    def wrap(*args, **kwargs):
        token = getattr(flask.request.authorization, "token", None)
        scopes = is_authorized(token)
        if scopes:
            flask.request.authorized_scopes = scopes
            return func(*args, **kwargs)

        return flask.abort(401, "Unauthorized Token")

    return wrap


def normalize_me(me):
    """
    Ensure that the `me` URI provided has a trailing slash for consistency.
    """

    if me.endswith("/"):
        return me

    return me + "/"


def verify_password(me, password):
    """
    Verify that the provided password matches the password specified
    in the configuration file.
    """

    me = normalize_me(me)
    pass_hash = hashlib.sha256(
        (password + conf.passwords["salt"]).encode("utf-8")
    ).hexdigest()
    print(pass_hash)
    found_pass = conf.passwords["passwords"].get(me)
    print(found_pass)
    return pass_hash == found_pass


def is_authorized(code):
    """
    Check the IndieAuth database for the provided code and return
    `False` if the code is not found, invalid, or expired. In the
    case that the code is valid, return the scopes that the code
    is authorized for.
    """

    record = authdb.sql(
        f"""
        select scope, expires from codes
        where code='{code}'
    """
    ).fetchone()

    if not record:
        return False

    now = arrow.get()
    expires = arrow.get(record[1])

    if now < expires:
        return record[0].split(" ")

    return False


def enforce_authorized_scope(scope):
    """
    HTTP endpoint methods can call this function to ensure that the
    authorization code in the current request context is authorized
    for the specified scope. If the scope is authorized, return `True`,
    otherwise, abort with a 401 HTTP response.
    """

    if scope in flask.request.authorized_scopes:
        return True
    flask.abort(401, f"Token not authorized for scope: {scope}")


def check_code(code, redirect_url, client_id):
    """
    For the specified code, redirect_url, and client_id,
    return the details (`created` datetime, `expires` datetime,
    `me` reference, and authorized `scope` list.
    """

    result = authdb.sql(
        f"""
        select created, expires, me, scope from codes where
        code='{code}' and
        client_id='{client_id}' and
        redirect_url='{redirect_url}'
    """
    ).fetchone()

    return dict(created=result[0], expires=result[1], me=result[2], scope=result[3])


def create_code(me, client_id, redirect_uri, scope, code, expires=None):
    """
    Create a new code in the IndieAuth database for the specified client,
    redirect url, state, response type, scopes, and code. Optionally, an
    expiration datetime can be specified. If an expiration is not specified,
    authorize the code for 100 years.
    """

    created = arrow.get()
    if not expires:
        expires = created.shift(years=+100)

    authdb.sql(
        f"""
        insert into codes(
            code,
            client_id,
            redirect_url,
            created,
            expires,
            me,
            scope
        ) values (
            '{code}',
            '{client_id}',
            '{redirect_uri}',
            '{created.isoformat()}',
            '{expires.isoformat()}',
            '{me}',
            '{scope}'
        )
    """
    )


@blueprint.route("/indieauth/auth", methods=["GET"])
def auth_get():
    """
    HTTP GET /indieauth/auth

    An external application identified by `client_id` is requesting
    authorization to perform the actions in `scope` on behalf of the
    user identified by the URL `me`. Once the process is complete,
    we should redirect to the specified `redirect_uri`.

    The external application may optionally provide a `state` parameter
    for its own purposes.

    If the application is only wanting identification, not authorization,
    then it will pass `response_type` as "id." If the application wants
    full authorization, then it will pass `response_type` as "code."
    """

    for arg in ("me", "client_id", "redirect_uri", "state", "response_type", "scope"):
        if arg not in flask.request.args:
            flask.abort(400, f"Invalid request: missing argument {arg}")

    me = normalize_me(flask.request.args["me"])

    return flask.render_template(
        "indieauth/auth.html",
        me=me,
        client_id=flask.request.args["client_id"],
        redirect_uri=flask.request.args["redirect_uri"],
        state=flask.request.args.get("state"),
        response_type=flask.request.args.get("response_type", "id"),
        scope=flask.request.args.get("scope", "create"),
    )


@blueprint.route("/indieauth/auth", methods=["POST"])
def auth_post():
    """
    HTTP POST /indieauth/auth

    If a `code` is passed into this endpoint, then we are to validate that
    authorization code against our cache with the `redirect_uri` and
    `client_id` parameters. If we find a match, we are to return the `me`
    URL that is associated with the authorization code.

    If a `code` is not passed into this endpoint, but `approve` is passed
    along as "Approve," then we generate an authorization token, and store
    it in our cache, before finally redirecting to the provided
    `redirect_uri`, passing along the `code` and `state`.
    """

    me = flask.request.form["me"]
    client_id = flask.request.form["client_id"]
    redirect_uri = flask.request.form["redirect_uri"]
    state = flask.request.form["state"]
    scope = flask.request.form["scope"]
    approve = flask.request.form["approve"]
    code = flask.request.form.get("code")
    password = flask.request.form["password"]

    me = normalize_me(me)

    if code is not None:
        found_code = check_code(
            code=code, redirect_url=redirect_uri, client_id=client_id
        )
        if found_code is not None:
            return dict(me=normalize_me(found_code["me"]))

        flask.abort(401, "Invalid auth code.")

    # otherwise approve request for auth code
    if approve == "Approve":
        # verify password
        if not verify_password(me, password):
            flask.abort(403, "Invalid password.")

        # generate auth code
        code = str(uuid.uuid4())

        # store code in our storage
        create_code(
            me=me,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code=code,
        )

        # redirect to the requesting application
        values = urlencode({"code": code, "state": state})
        uri = redirect_uri + "?" + values
        return flask.redirect(uri)


@blueprint.route("/indieauth/token", methods=["GET"])
def token_get():
    """
    GET /indieauth/token

    Verify an access token that is provided in the `Authorization`
    header as a `Bearer` token.
    """

    response = flask.Response()

    # pull the token off the Authorization header
    token = flask.request.headers.get("Authorization", "Bearer X").split(" ")[1]

    # validate token
    try:
        payload = jwt.decode(
            token, conf.token["secret"], algorithms=[conf.token["algorithm"]]
        )
        if payload.get("response_type") == "id":
            response.status = 400
            return {"error": "invalid_grant"}

        return flask.render_template(
            "indieauth/urlencode.html",
            me=normalize_me(payload["me"]),
            client_id=payload["client_id"],
            scope=payload["scope"],
        )
    except Exception:
        flask.abort(403, "Invalid token.")


@blueprint.route("/indieauth/token", methods=["POST"])
def token_post():
    """
    POST /indieauth/token

    An external application is requesting an access token. They have
    an authorization `code` for the user identified by `me`. We will
    verify the code, and then redirect to the `redirect_uri`, providing
    the verified `me` and `scope` associated with the access `code`.
    """

    code = flask.request.args.get("code")
    me = flask.request.args.get("me")
    redirect_uri = flask.request.args.get("redirect_uri")
    client_id = flask.request.args.get("client_id")

    # look for a matching authorization code
    found_code = check_code(code=code, redirect_uri=redirect_uri, client_id=client_id)

    # if we found one, generate and store a token
    me = normalize_me(me)
    if found_code is not None and normalize_me(found_code["me"]) == me:
        # generate a token
        token = jwt.encode(
            {
                "me": me,
                "client_id": client_id,
                "scope": found_code["scope"],
                "date_issued": str(datetime.utcnow()),
                "nonce": str(uuid.uuid4()),
            },
            conf.token["secret"],
            conf.token["algorithm"],
        ).decode("utf-8")

        # construct the return payload
        data = {
            "me": normalize_me(found_code["me"]),
            "scope": found_code["scope"],
            "access_token": token,
        }

        return flask.render_template("indieauth/urlencode.html", data)

    # if we didn't find one, reject the request
    flask.abort(401, "Invalid auth code.")
