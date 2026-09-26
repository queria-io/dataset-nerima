{# 防災井戸のステージング。原典は緯度経度の列を持つが全行空なので、
   地図に出せる座標は住所からのジオコーディングだけが供給する。 #}

{{ ods_geocoded_source('raw_disaster_well') }}
select
    category,
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
    url,
    image,
    image_license,
    notes,
    _extras as extras,
    _source_title as source_title,
    _source_url as source_url,
    _source_page as source_page
from geocoded
