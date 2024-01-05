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
from raw_content;
