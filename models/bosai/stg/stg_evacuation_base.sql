{# 避難拠点のステージング。原典は座標を持つので、住所からの補完は効かせるだけ効かせる。 #}

{{ ods_geocoded_source('raw_evacuation_base') }}
select
    name,
    address,
    try_cast(lat as double) as lat,
    try_cast(lon as double) as lon,
    {{ ods_geo_columns(geocoded=true) }},
    _extras as extras,
    _source_title as source_title,
    _source_url as source_url,
    _source_page as source_page
from geocoded
