"""
Dwell data module, which includes convenient classes representing many
different "kinds" of content, all of which inherit from the base `Post` class.
Data is queried from a DuckDB database, which can be quickly regenerated on
demand. All data is stored on-disk as a Hive-Partitioned directory structure:

    `content/year=<year>/month=<month>/day=<day>/<post-id>.json`

Data is expected to be in MF2 JSON format.

To query all kinds of post, use the `Post.query` classmethod. To query a
specific kind of post, use the relevant subclass' classmethod of the same
name.

This module also provides a simple convenience interface for directly querying
the DuckDB content database using SQL.
"""


import concurrent.futures
import json
import pathlib
import threading
import urllib.parse

import arrow
import duckdb


class classproperty:
    def __init__(self, func):
        self.fget = func

    def __get__(self, _, owner):
        return self.fget(owner)


class DatabaseManager:
    def __init__(self):
        self._conn = None
        self._migrating = threading.Lock()
        self._reinitializing = threading.Lock()

    def connect(self, filename="content.db", read_only=False):
        self._conn = duckdb.connect(filename, read_only=read_only)

    @property
    def connection(self):
        with self._migrating:
            return self._conn

    def disconnect(self):
        if self._conn:
            self._conn.close()

    def _initialize(self, connection):
        connection.sql(
            """
            PRAGMA memory_limit=-1;
            create table raw_content
            as
            select *
            from read_json_auto(
                'content/**/*.json',
                format='auto',
                records=true,
                maximum_depth=1,
                hive_partitioning='true',
                filename='true'
            );
            create view content as select
                properties->'post-id'->>0 "uuid",
                properties->'post-kind'->>0 "kind",
                properties->'url'->>0 "url",
                coalesce(
                    (properties->'deleted'->>0), false
                )::JSON::BOOL "deleted",
                json_extract("properties",
                    '$."published"[0]')::JSON::TIMESTAMP "published",
                json_extract("properties",
                    '$."location-metadata"')::JSON::STRUCT(
                        "timestamp" timestamp,
                        x float,
                        y float,
                        altitude int,
                        motion varchar[],
                        wifi varchar,
                        battery_level float,
                        battery_state varchar,
                        speed int,
                        year int,
                        month int,
                        day int,
                        hour int,
                        minute int
                    ) "location",
                properties,
                children,
                filename,
                year,
                month,
                day
            from raw_content;"""
        )

    def add(self, path):
        self.connection.sql(
            f"""
            insert into raw_content
            select * from
            read_json_auto(
                '{path}',
                format='auto',
                records=true,
                maximum_depth=1,
                hive_partitioning='true',
                filename='true'
            );"""
        )

    def _migrate(self, to_filename, from_filename):
        print("Initialization complete, migrating to new database.")
        with self._migrating:
            self.disconnect()
            pathlib.Path(from_filename).rename(pathlib.Path(to_filename))
            self.connect(filename=to_filename, read_only=True)
        print("Migration complete!")

    def reinitialize(self, target_filename="content.db"):
        self._reinitializing.acquire()

        print("Reinitializing database from disk...")

        temp_filename = f"{target_filename}.initializing"

        def create_database():
            conn = duckdb.connect(temp_filename)
            self._initialize(conn)

        def done(future):
            if future.done():
                error = future.exception()
                if error:
                    print("{}: error returned: {}".format(future.arg, error))
                    self._reinitializing.release()
                else:
                    self._migrate(
                        from_filename=temp_filename, to_filename=target_filename
                    )
                    self._reinitializing.release()

        executor = concurrent.futures.ThreadPoolExecutor()
        future = executor.submit(create_database)
        future.add_done_callback(done)

        return True


database = DatabaseManager()
database.connect()

kind_map = {}
kind_aliases = {"default": []}


class Author:
    """
    Represents an `h-card` for an author of content on a site.
    """

    def __init__(self, h_card=None, photo=None, name=None, url=None):
        self.name = name
        self.photo = photo
        self.url = url

        if h_card:
            self.photo = h_card["properties"]["photo"][0]
            self.name = h_card["properties"]["name"][0]
            self.url = h_card["properties"]["url"][0]


class Comment:
    """
    Represents an `h-cite` for a comment on a piece of content.
    """

    def __init__(self, h_cite):
        self.summary = h_cite["properties"]["summary"][0]
        self.content = h_cite["properties"]["content"][0]["html"]
        self.text = h_cite["properties"]["content"][0]["value"]
        self.author = Author(h_cite["properties"]["author"][0])
        self.url = h_cite["properties"]["url"][0]

    @property
    def source(self):
        url = urllib.parse.urlparse(self.url)
        return url.hostname


class Like:
    """
    Represents an `h-cite` for a like/star on a piece of content.
    """

    def __init__(self, h_cite):
        self.author = Author(h_cite["properties"]["author"][0])
        self.url = h_cite["properties"]["url"][0]
        self.published = arrow.get(h_cite["properties"]["published"][0])

    @property
    def source(self):
        url = urllib.parse.urlparse(self.url)
        return url.hostname


class Post:
    """
    The heart of the Dwell content data model. Every post on the site
    is a subclass of this class. It provides many consistent convenience
    methods and properties for interacting with content in the content
    store.
    """

    __aliases__ = []
    __kind__ = "generic"
    __kind_name__ = "Generic Posts"
    __kind_icon__ = "document-text-outline"

    def __init__(self, mf2, children, filename):
        """
        Construct a representation of the specified post from the
        included MF2 JSON dictionary, list of children, and filename
        on disk.
        """

        self.mf2 = mf2
        self.children = children
        self.filename = filename

    def __str__(self):
        parts = [f"{self.__class__.__name__}: {self.url}"]

        if self.content:
            parts.append(f': {self.content["html"]}')

        return "".join(parts)

    @classmethod
    def all_kinds(cls):
        mapping = {}
        for kind_key, kind_cls in kind_map.items():
            if kind_key == "staticpage":
                continue
            mapping[kind_key] = kind_cls.__kind_name__
        return mapping

    @property
    def content(self):
        """
        Convenience property for the content record on this post.
        """
        content = self.mf2.get("content", [{"html": "", "text": ""}])
        if content and len(content):
            return content[0]
        return {}

    # convenience properties for metadata about this post's kind and
    # associated metadata
    kind = classproperty(lambda self: self.__kind__)
    kind_name = classproperty(lambda self: self.__kind_name__)
    kind_icon = classproperty(lambda self: self.__kind_icon__)

    # convenience properties for fetching the raw, on-disk JSON representation
    # for this post, the MF2 data structure that has been parsed, and the HTML
    # content or text value within the post
    raw = property(lambda self: json.loads(open(self.filename, "rb").read()))
    json = property(lambda self: {"type": ["h-entry"], "properties": self.mf2})
    html = property(lambda self: self.content["html"])
    value = property(lambda self: self.content["value"])

    # convenience properties for the name, author, url, syndication references,
    # post identifier, publish datetime, location metadata, soft delete status,
    # comments, likes, and photos on this post
    name = property(lambda self: self.mf2.get("name", [""])[0])
    author = property(lambda self: Author(self.mf2["author"][0]))
    url = property(lambda self: self.mf2["url"][0])
    syndication = property(lambda self: self.mf2["syndication"])
    uuid = property(lambda self: self.mf2["post-id"][0])
    published = property(lambda self: arrow.get(self.mf2["published"][0]))
    location = property(lambda self: self.mf2.get("location-metadata"))
    deleted = property(lambda self: self.mf2.get("deleted", [False])[0])
    comments = property(lambda self: [Comment(h) for h in self.mf2.get("comment", [])])
    likes = property(lambda self: [Like(h) for h in self.mf2.get("like", [])])
    photos = property(lambda self: self.mf2.get("photo", []))

    @classmethod
    def _get(cls, uuid=None, slug=None, year=None):
        """
        Internal class method for fetching a specific post by
        UUID, slug, or year and partial slug. Does not return an
        instance of Post, but raw columnar data from the database.
        """

        sql = "select * from content where "
        if uuid:
            sql += f"uuid = '{uuid}'"
        elif slug:
            if year:
                sql += f"url = '/{year}/{slug}'"
            else:
                sql += f"url = '{slug}'"
        else:
            raise Exception("Please provide a uuid or slug.")

        if year:
            sql += f" and datepart('year', published) = {year}"

        result = database.connection.sql(sql).fetchall()
        return result[0] if result else None

    @classmethod
    def _instantiate(cls, record):
        """
        Internal class method for instantiating an instance of the
        correct Post subclass for the specified DuckDB record for a
        specific post.
        """

        kind = record[1].lower() if record[1] else None
        return kind_map.get(kind, cls)(
            mf2=json.loads(record[6]),
            children=json.loads(record[7]) if record[7] else [],
            filename=record[8],
        )

    @classmethod
    def get(cls, uuid=None, slug=None, year=None):
        """
        Fetch a post by its UUID, slug, or partial slug and publication year.
        Returns an instance of the appropriate subclass of Post.
        """

        record = cls._get(uuid=uuid, slug=slug, year=year)
        return cls._instantiate(record) if record else None

    @classmethod
    def query(
        cls,
        start=None,
        end=None,
        limit=20,
        offset=0,
        sort="desc",
        month=None,
        day=None,
        year=None,
        kinds=None,
        count=False,
    ):
        """
        Query the post database and return a list of Post subclass instances.

        Arguments:
        - `start` is a datetime that specifies the earliest date and time for
          the queried post publication date and time.
        - `end` is a datetime that specifies the latest date and time for the
           queried post publication date and time.
        - `limit` is an integer limit to the maximum number of posts to return,
          which defaults to 20.
        - `offset` is an integer specifying the offset index within the queried
          data set. In combination with `limit` this is used for pagination.
        - `sort` is either `asc` or `desc`, specifying the order by publish
          date and time in the query.
        - `month` is an integer allowing to filter by publish month.
        - `day` is an integer allowing to filter by publish day.
        - `year` is an integer allowing to filter by publish year.
        - `kinds` is a list of post kinds or kind aliases to filter by.
        - `count` is a boolean that defaults to `False`. If `True`, the method
          will return the total number of posts that match the query.
        """

        parts = []

        where = ["deleted = false"]
        if start and end:
            where.extend(
                [
                    f"published >= '{start.isoformat()}'",
                    f"published <= '{end.isoformat()}'",
                ]
            )

        if year:
            where.append(f"year = {year}")

        if month:
            where.append(f"month = {month}")

        if day:
            where.append(f"day = {day}")

        if cls.__name__ != "Post":
            kinds = [cls.__kind__]

        if kinds:
            kinds = [kind.capitalize() for kind in kinds]
            where.append(f"kind in {str(tuple(kinds))}")

        # TODO: fix this on the ingest side
        where.append("kind != 'UnfurledUrl'")
        where.append("kind != 'StaticPage'")

        if count:
            sql = "select count(*) from content" + " ".join(parts)
            if where:
                sql += " where " + " and ".join(where)
            result = database.connection.sql(sql).fetchone()[0]
            return result

        paging = [f"order by published {sort}", f"limit {limit}", f"offset {offset}"]

        sql = "select * from content" + " ".join(parts)
        if where:
            sql += " where " + " and ".join(where)

        sql += " " + " ".join(paging)

        results = database.connection.sql(sql)
        posts = []
        for result in results.fetchall():
            posts.append(cls._instantiate(result))
        return posts


class Blog(Post):
    """
    Post kind representing a blog post.
    """

    __kind__ = "entry"
    __kind_name__ = "Blog Posts"
    __kind_icon__ = "document-text-outline"
    __aliases__ = ["posts"]

    title = property(lambda self: self.mf2["name"][0])


class Bookmark(Post):
    """
    Post kind representing a variety of interaction types: likes, bookmarks,
    and reposts.
    """

    __kind__ = "like"
    __kind_name__ = "Interactions"
    __kind_icon__ = "magnet"
    __aliases__ = ["bookmarkedpages"]

    name = property(lambda self: self.mf2["name"][0])
    is_like = property(lambda self: bool(self.mf2.get("like-of")))
    is_bookmark = property(lambda self: bool(self.mf2.get("bookmark-of")))
    is_repost = property(lambda self: bool(self.mf2.get("repost-of")))

    @property
    def icon(self):
        if self.is_bookmark:
            return "bookmark-outline"
        elif self.is_like:
            return "thumbs-up-outline"
        else:
            return "repeat-sharp"

    @property
    def target(self):
        if self.is_like:
            return self.mf2["like-of"][0]
        elif self.is_bookmark:
            return self.mf2["bookmark-of"][0]
        else:
            return self.mf2["repost-of"][0]


class Status(Post):
    """
    Post kind representing a short, microblog post or status update.
    """

    __kind__ = "status"
    __kind_name__ = "Microblog Posts"
    __kind_icon__ = "chatbox-ellipses-outline"
    __aliases__ = ["statusupdates"]


class Product:
    """
    Representation of a "product," mostly used as a reference to a movie or TV
    show.
    """

    def __init__(self, mf2):
        self.mf2 = mf2

    photo = property(lambda self: self.mf2["properties"]["photo"][0])
    name = property(lambda self: self.mf2["properties"]["name"][0])
    url = property(lambda self: self.mf2["properties"]["url"][0])


class Watch(Post):
    """
    Post kind representing a post about a TV show or movie that has been
    "watched."
    """

    __kind__ = "watching"
    __kind_name__ = "TV and Movie History"
    __kind_icon__ = "film-outline"

    watch_of = property(lambda self: Product(self.mf2["item"][0]))


class Reply(Post):
    """
    Post kind representing a response/reply to another piece of content,
    generally not on this site.
    """

    __kind__ = "reply"
    __kind_name__ = "Replies"
    __kind_icon__ = "arrow-redo-circle-outline"
    __aliases__ = ["replies"]

    @property
    def in_reply_to(self):
        if "in-reply-to" not in self.mf2:
            return ""
        return self.mf2["in-reply-to"][0]


class Photo(Post):
    """
    Post kind for individual photos or galleries of multiple photos.
    """

    __kind__ = "photo"
    __kind_name__ = "Photos"
    __kind_icon__ = "image-outline"
    __aliases__ = ["photos"]

    is_gallery = property(lambda self: len(self.photos) > 1)


class Location:
    """
    Representation of a location referred to as an "h-card" within a post.
    """

    def __init__(self, h_card):
        self.name = self._property(h_card, "name")
        self.latitude = self._property(h_card, "latitude", float)
        self.longitude = self._property(h_card, "longitude", float)

    def __getitem__(self, key):
        return getattr(self, key, None)

    def __contains__(self, key):
        return key in ("name", "latitude", "longitude")

    def _property(self, h_card, name, cast=str):
        value = h_card["properties"].get(name, [None])[0]
        return cast(value) if value else None


class Checkin(Post):
    """
    Post kind representing a "checkin" to a specific location.
    """

    __kind__ = "checkin"
    __kind_name__ = "Checkins"
    __kind_icon__ = "navigate-circle-outline"
    __aliases__ = ["locations"]

    checkin_to = property(lambda self: Location(self.mf2["location"][0]))
    html = property(lambda self: f"Checked into {self.checkin_to.name}")


class ListenOf:
    """
    Representation of a podcast that has been listened to, referred to via
    an "h-cite" within the post.
    """

    def __init__(self, h_cite):
        self.name = h_cite["properties"].get("name", ["Listened To"])[0]
        self.content = h_cite["properties"]["content"][0]["html"]
        self.url = h_cite["properties"]["listen-of"][0]

        if h_cite["properties"].get("photo"):
            self.photo = h_cite["properties"].get("photo", [None])[0]


class Listen(Post):
    """
    Post kind representing to a record of listening to a podcast.
    """

    __kind__ = "listen"
    __kind_name__ = "Podcast History"
    __kind_icon__ = "mic-circle-outline"

    listen_of = property(lambda self: ListenOf(self.children[0]))
    name = property(lambda self: self.listen_of.name)


class Page(Post):
    """
    Post kind representing a static page on the website.
    """

    __kind__ = "staticpage"
    __kind_name__ = "Pages"
    __kind_icon__ = "document-text-outline"
    __aliases__ = ["pages"]


class PlayOf:
    """
    Representation of a video game that has been played.
    """

    def __init__(self, name, photo):
        self.name = name
        self.photo = photo


class Play(Post):
    """
    Post kind for recording a session of playing a video game.
    """

    __kind__ = "play"
    __kind_name__ = "Gaming History"
    __kind_icon__ = "game-controller-outline"
    __aliases__ = ["playing"]

    @property
    def play_of(self):
        return PlayOf(name=self.name, photo=self.mf2["photo"][0])


class Recipe(Post):
    """
    Post kind representing a recipe.
    """

    __kind__ = "recipe"
    __kind_name__ = "Recipes"
    __kind_icon__ = "fast-food-outline"
    __aliases__ = ["recipes"]

    name = property(lambda self: self.children[0]["properties"]["name"][0])
    ingredients = property(lambda self: self.children[0]["properties"]["ingredient"])
    duration = property(lambda self: self.children[0]["properties"]["duration"][0])
    yields = property(lambda self: self.children[0]["properties"]["yield"][0])
    instructions = property(
        lambda self: self.children[0]["properties"]["instructions"][0]
    )
    photo = property(
        lambda self: self.children[0]["properties"].get("photo", [None])[0]
    )

    @property
    def content(self):
        return self.instructions


class ReviewOf:
    """
    Represents a reference to something being reviewed.
    """

    def __init__(self, mf2):
        self.url = mf2["properties"]["url"][0]
        self.name = mf2["properties"]["name"][0]
        if mf2["properties"].get("photo"):
            self.photo = mf2["properties"]["photo"][0]
        else:
            self.photo = None


class Review(Post):
    """
    Post kind representing a review of a specific thing.
    """

    __kind__ = "review"
    __kind_name__ = "Reviews"
    __kind_icon__ = "star-half-outline"
    __aliases__ = ["reviews"]

    rating = property(lambda self: int(self.mf2["rating"][0]))
    review_of = property(lambda self: ReviewOf(self.mf2["item"][0]))


class RSVP(Post):
    """
    Post kind representing an RSVP.
    """

    __kind__ = "rsvp"
    __kind_name__ = "RSVPs"
    __kind_icon__ = "checkmark-done-circle-outline"
    __aliases__ = ["rsvps"]

    response = property(lambda self: self.mf2["rsvp"][0])


# create a mapping table from post kinds and aliases to Post subclasses
def add_alias(alias, kind):
    kind_aliases.setdefault(alias, []).append(kind)


def get_kinds_for_alias(alias):
    return kind_aliases.get(alias, [])


for subclass in Post.__subclasses__():
    kind_map[subclass.__kind__] = subclass
    kind_aliases.setdefault(subclass.__kind__, []).append(subclass)
    for alias in subclass.__aliases__:
        add_alias(alias, subclass)
