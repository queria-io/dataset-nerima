{# ジオコーディング結果のステージング。住所1件につき1行で、
   採用できる座標が無い行は geo_lat / geo_lon / geo_level が NULL。 #}

select
    address,
    geo_lat,
    geo_lon,
    geo_level,
    lg_code,
    machiaza_id,
    match_level
from {{ ref('raw_geocode') }}
