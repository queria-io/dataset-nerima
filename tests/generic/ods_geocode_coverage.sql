{# 住所を持つ行のうち、地図に出せる座標が入った割合の下限を見る。

   ods_geo_coverage が見るのは原典の座標の取りこぼしだけで、ジオコーディングが
   丸ごと効かなくなっても素通りする。住所キーの作り方が SQL と Python でずれると
   左結合が全件外れ、補完が静かに 0 件になる。その壊れ方をここで捕まえる。

   分母は住所がある行。ジオコーディングの成否は住所の有無で決まり、原典の座標が
   あるかどうかとは独立している。

   既定の 0.90 は実測から取る。練馬区は住所 234 件すべてが解決し、bosai の4表とも
   1.000（2026-09-26 時点）。市区町村の代表点は pipelines/geocode.py の段階で
   落としているので、この比率には入らない。 #}

{% test ods_geocode_coverage(model, address='address', min_ratio=0.90) %}

{%- set with_address = "count(*) filter (where nullif(trim(" ~ address ~ "), '') is not null)" -%}
{%- set with_geo = "count(*) filter (where nullif(trim(" ~ address ~ "), '') is not null and geo_lat is not null)" -%}

select
    {{ with_address }} as address_rows,
    {{ with_geo }} as located_rows,
    {{ with_geo }} * 1.0 / {{ with_address }} as ratio
from {{ model }}
having {{ with_address }} > 0
   and {{ with_geo }} * 1.0 / {{ with_address }} < {{ min_ratio }}

{% endtest %}
