# Dwell: An IndieWeb CMS for Personal Websites

Dwell is a simple CMS for creating your own
[indieweb](https://indieweb.org "IndieWeb") website, including support
for [micropub](https://www.w3.org/TR/micropub/ "Micropub"),
[indieauth](https://indieweb.org/IndieAuth "IndieAuth"), and
[webmention](https://www.w3.org/TR/webmention/ "Webmention"). Dwell
was created to power the personal site of
[cleverdevil](https://cleverdevil.io "Jonathan LaCour"), which currently
runs the [known](https://github.com/idno/known "Known") content
management system. Under the hood, Dwell is built in the
[python](https://python.org "Python") programming language, and uses
[duckdb](https://duckdb.org "DuckDB") for its query engine, though all
content is stored on-disk as `JSON` files contained within a
[hive](https://duckdb.org/docs/data/partitioning/hive_partitioning.html "Hive")
partitioned directory structure.

## Why?

For many years, I have had my own site. In fact, my current website
includes a massive [archive](https://cleverdevil.io/archive "archive")
all of my content starting from 2002! I have even migrated all of the
content I posted on Instagram, Twitter, and Facebook before I left those
silos entirely after they became cesspools of misinformation and
surveillance capitalism owned and operated by billionaires with values
that do not align with my own.

My current site runs on [known](https://github.com/idno/known "Known"),
which has served me well. While I am able to write PHP, it is absolutely not my
language of choice or expertise. In addition, I would like to make my site more
lightweight, with as few dependencies as possible, and no need for complex
relational databases.

Why not use something like WordPress? Yes, WordPress has the benefit of
a massive community, but is essentially a giant pile of legacy. I have a
lot of experience with that community, and I think its lovely, but isn’t
really focused on what I care about, and has all of the same complexity
issues as Known, with the downside of being an absolute security
nightmare.

Why not a static site generator? I considered it, but I like the ability
to create extremely dynamic pages. With DuckDB, I get all of the
benefits of a relational database with none of the operational pain.

Lastly, because its fun. I love working on my site!

## Technical Details

Content is stored on disk as JSON files in a directory structure that is
partitioned based upon date, as follows:

    content/
        year=2023/
            month=11/
                day=12/
                    post-uuid.json

Dwell uses the aforementioned DuckDB to make the entire content
directory queryable with SQL, without the need to run a separate,
heavyweight database server. Very large sites with tens of thousands of
posts can be completely indexed by Dwell in a matter of a few seconds.
The complete content is stored in a table called `raw_content` within
the `content.db` database, and a convenience view called `content` is
created which makes the data easier to interact with.

## Status

This is early. Very early. The first focus has been proving out the data
storage, indexing, and querying mechanism using DuckDB. Below is a list
(that is likely incomplete) of features, including what is done, and
what is in-progress.

- [x] Consume and index a hive-partitioned directory of MF2 JSON
- [x] Storage and index support for post kinds
  - [x] Blog
  - [x] Status
  - [x] Bookmark
  - [x] Watch
  - [x] Play
  - [x] Reply
  - [x] Photo
  - [x] Checkin
  - [x] Listen
  - [x] Recipe
  - [x] Review
  - [x] RSVP
- [x] Query for posts
  - [x] Get by post id
  - [x] Query by date range and post kind
  - [x] Ordering, limit, and offset
- [x] Micropub support
  - [x] Create content
    - [x] MF2 JSON
    - [x] Form encoded
    - [x] Multipart form
  - [x] Update content
  - [x] Delete content
  - [x] Undelete content
  - [x] Media endpoint
  - [ ] Syndication
    - [ ] Mastodon
    - [ ] Bluesky
- [ ] IndieAuth support
    - [x] Token database
    - [x] Password configuration
    - [x] Micropub endpoint enforcement
    - [x] User-facing auth flow
    - [ ] User-facing auth flow beautification
    - [ ] Separate IndieAuth code
- [ ] Webmention
- [ ] Move all post kinds to plugins, other than Blog, Status, and Photo
- [ ] Website views
  - [x] Home stream
  - [x] Custom streams
  - [x] Monthly summaries
  - [x] On this day
  - [x] Photos page
  - [ ] Static pages
  - [x] Profile
  - [x] Archive
  - [x] Now
  - [x] Overview
  - [ ] Make all streams and post kinds use proper microformats
- [ ] Forms for authenticated users to create all “kinds” of content
- [x] Fixing ingestion for specific types and content that is missed
  - [x] Recipe
  - [x] Like / Repost kind
  - [x] Interactions (likes, primarily)

At first, I will entirely focus on getting my own website fully
functional on-top of Dwell, to enable me to migrate off of Known, but I am
actively seeking collaborators that are interested in a shared codebase for
building our own sites.
