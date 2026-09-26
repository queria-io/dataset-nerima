{# 練馬区の緯度経度から「地図に出せる座標」を決める。

   原典の lat / lon は補正せずに残し、地図に使える座標を geo_lat / geo_lon として別に持たせる。
   原典に使える座標が無い行は、住所を ABR（アドレス・ベース・レジストリ）で
   ジオコーディングした座標で補う。原典の座標は常に優先する。

   geo_source は採用した値の由来。
     source          原典の緯度経度をそのまま採用した
     source_swapped  原典の緯度と経度が入れ替わっていたので入れ替えて採用した
     abr             原典に使える座標が無く、住所から求めた座標を採用した
     NULL            採用できる座標がない

   geo_level は座標の粒度。原典由来の座標は粒度が申告されないので 'source' 固定。
   ABR 由来は abr-geocoder の coordinate_level をそのまま入れる
   （residential_detail / residential_block / machiaza_detail / machiaza）。
   市区町村代表点は地図に出すと区役所にピンが集まるだけなので、
   pipelines/geocode.py の段階で落としてある。 #}

{# 値域は練馬区ではなく日本全域にとる。所在地が区外になる行が実在し、
   区域に絞ると原典の正しい座標を捨ててしまうため。
   緯度域 [20.0, 46.0] と経度域 [122.0, 154.5] は重ならないので、これでも入れ替わりは
   一意に判定できる（緯度に 139 が入れば緯度域を外れ、経度に 35 が入れば経度域を外れる）。
   端は沖ノ鳥島 北緯 20.42 / 択捉島 北緯 45.55 / 与那国島 東経 122.93 / 南鳥島 東経 153.98。 #}
{% macro ods_geo_in_range(lat, lon) -%}
({{ lat }} between 20.0 and 46.0 and {{ lon }} between 122.0 and 154.5)
{%- endmacro %}

{# geocoded=true にすると、原典に使える座標が無い行を abr_lat / abr_lon / abr_level で
   補う。この3列は ods_geocoded_source が用意する。 #}
{% macro ods_geo_columns(lat='try_cast(lat as double)', lon='try_cast(lon as double)',
                         geocoded=false) -%}
{%- set abr_lat = 'abr_lat' if geocoded else 'null' -%}
{%- set abr_lon = 'abr_lon' if geocoded else 'null' -%}
{%- set abr_level = 'abr_level' if geocoded else 'null' -%}
case
        when {{ ods_geo_in_range(lat, lon) }} then {{ lat }}
        when {{ ods_geo_in_range(lon, lat) }} then {{ lon }}
        else {{ abr_lat }}
    end as geo_lat,
    case
        when {{ ods_geo_in_range(lat, lon) }} then {{ lon }}
        when {{ ods_geo_in_range(lon, lat) }} then {{ lat }}
        else {{ abr_lon }}
    end as geo_lon,
    case
        when {{ ods_geo_in_range(lat, lon) }} then 'source'
        when {{ ods_geo_in_range(lon, lat) }} then 'source_swapped'
        when {{ abr_lat }} is not null then 'abr'
    end as geo_source,
    case
        when {{ ods_geo_in_range(lat, lon) }} or {{ ods_geo_in_range(lon, lat) }} then 'source'
        else {{ abr_level }}
    end as geo_level
{%- endmacro %}

{# 地図表示用のジオメトリ。座標が無い行は NULL にする。
   ST_Point(NULL, NULL) はジオメトリを返してしまい、地図プレビューの件数に混ざる。
   1 テーブルに GEOMETRY 列は 1 本だけにすること（プレビュー生成も queria-web も
   最初の GEOMETRY 列しか見ない）。 #}
{% macro ods_geometry(lat='geo_lat', lon='geo_lon') -%}
case when {{ lat }} is not null then st_point({{ lon }}, {{ lat }}) end
{%- endmacro %}


{# ジオコーディング結果を左結合した生データ。stg モデルの先頭に置き、`from geocoded` で受ける。

   突合キーは住所そのもの。pipelines/geocode.py は原典の住所文字列をそのまま
   address 列に出すので、SQL 側では trim だけで引ける。正規化を両側に置くと
   片方を直したときに静かに 0 件になるため、正規化は pipelines 側だけに持たせる。 #}
{# 結合先の stg_geocode も address 列を持つので、必ず別名で修飾する。
   修飾を落とすと Ambiguous reference で dbt build が落ちる #}
{% macro ods_geocoded_source(raw) -%}
with source as (
    select * from {{ ref(raw) }}
),
geocoded as (
    select
        source.*,
        g.geo_lat as abr_lat,
        g.geo_lon as abr_lon,
        g.geo_level as abr_level
    from source
    left join {{ ref('stg_geocode') }} as g
        on g.address = trim(source.address)
)
{%- endmacro %}
