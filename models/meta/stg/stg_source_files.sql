{{ config(materialized='ephemeral') }}

-- raw_source_files を mart から読むための stg。列は raw のまま
SELECT * FROM {{ ref('raw_source_files') }}
