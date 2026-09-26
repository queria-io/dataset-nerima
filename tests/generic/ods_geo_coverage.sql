{# 原典が緯度経度を持つ行のうち、原典の座標を採用できた割合の下限を見る。

   ods_geo_consistent が見る不変条件は ods_geo_columns の構成から自動的に成り立つので、
   値域を書き間違えて大半の行を落としても「一貫して NULL」になるだけで検出できない。
   ビルドは無人で走り push まで進むため、件数側の下限をここで押さえる。

   分母は「原典が緯度と経度の対を持つ行」にする。count(lat) だと経度が欠けた行も数え、
   自治体が緯度だけ公開した CSV を出すとこちらのロジックが変わっていなくても比率が
   下がる。取得元の不備でビルドが落ちると、データセット全体の公開が止まってしまう。

   分子は geo_source が原典由来の行に限る。count(geo_lat) だとジオコーディングで
   補った行も数えてしまい、比率が 1 を超えて検査が素通りする。ここで見たいのは
   「原典の座標を取りこぼしていないか」だけで、補完の効きは
   ods_geocode_coverage が別に見る。

   既定の 0.95 は実測（ods の16種別すべてで 0.98 以上、最小は ods.event の 0.990。
   childcare の2表はいずれも 1.000）から取る。 #}

{% test ods_geo_coverage(model, min_ratio=0.95) %}

{%- set source_rows = "count(*) filter (where lat is not null and lon is not null)" -%}
{%- set adopted = "count(*) filter (where geo_source in ('source', 'source_swapped'))" -%}

select
    {{ source_rows }} as source_rows,
    {{ adopted }} as adopted_rows,
    {{ adopted }} * 1.0 / {{ source_rows }} as ratio
from {{ model }}
having {{ source_rows }} > 0
   and {{ adopted }} * 1.0 / {{ source_rows }} < {{ min_ratio }}

{% endtest %}
