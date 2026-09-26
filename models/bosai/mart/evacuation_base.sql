-- 避難拠点（練馬区立小中学校に設置される拠点）
select
    name,
    address,
    lat,
    lon,
    geo_lat,
    geo_lon,
    geo_source,
    geo_level,
    {{ ods_geometry() }} as geometry,
    extras,
    source_title,
    source_url,
    source_page
from {{ ref('stg_evacuation_base') }}
