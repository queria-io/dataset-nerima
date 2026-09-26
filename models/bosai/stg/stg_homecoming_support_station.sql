{# 帰宅支援ステーションのステージング。災害種別を BOOLEAN に正規化する。 #}

{% set flags = [
    'for_flood', 'for_landslide', 'for_storm_surge', 'for_earthquake',
    'for_tsunami', 'for_large_fire', 'for_inland_flooding', 'for_volcano',
    'shelter_overlap',
] %}

{{ ods_geocoded_source('raw_homecoming_support_station') }}
select
    municipality_code,
    municipality_name,
    address_municipality_code,
    facility_id,
    name,
    name_kana,
    name_en,
    town_id,
    address,
    prefecture,
    city,
    town,
    street_number,
    building_name,
    try_cast(lat as double) as lat,
    try_cast(lon as double) as lon,
    {{ ods_geo_columns(geocoded=true) }},
    try_cast(elevation as double) as elevation,
    phone_number,
    extension,
    contact_email,
    contact_form_url,
    contact_note,
    postal_code,
    {% for flag in flags %}
    {{ ods_flag(flag) }} as {{ flag }},
    {% endfor %}
    url,
    image,
    image_license,
    notes,
    _extras as extras,
    _source_title as source_title,
    _source_url as source_url,
    _source_page as source_page
from geocoded
