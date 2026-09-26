{# 災害時給水ステーションのステージング。種別のフラグを BOOLEAN に正規化する。
   確保水量は「1500立方メートル」のような自由記述なので原文のまま残す。 #}

{% set flags = [
    'water_type_purification', 'water_type_emergency_tank', 'water_type_small_tank',
] %}

{{ ods_geocoded_source('raw_emergency_water_station') }}
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
    secured_volume,
    url,
    image,
    image_license,
    notes,
    _extras as extras,
    _source_title as source_title,
    _source_url as source_url,
    _source_page as source_page
from geocoded
