{# 住所のジオコーディング結果の生データ。
   pipelines/geocode.py が防災設備の住所を abr-geocoder（アドレス・ベース・レジストリ）に
   通して data/geocode/addresses.ndjson に保存する。1行 = 原典の住所1件。 #}

{{ config(materialized='table') }}

select *
from read_json(
    'data/geocode/addresses.ndjson',
    format='newline_delimited',
    columns={
        'address': 'VARCHAR',
        'geo_lat': 'DOUBLE',
        'geo_lon': 'DOUBLE',
        'geo_level': 'VARCHAR',
        'lg_code': 'VARCHAR',
        'machiaza_id': 'VARCHAR',
        'pref': 'VARCHAR',
        'city': 'VARCHAR',
        'ward': 'VARCHAR',
        'oaza_cho': 'VARCHAR',
        'chome': 'VARCHAR',
        'koaza': 'VARCHAR',
        'blk_num': 'VARCHAR',
        'rsdt_num': 'VARCHAR',
        'rsdt_num2': 'VARCHAR',
        'match_level': 'VARCHAR'
    }
)
