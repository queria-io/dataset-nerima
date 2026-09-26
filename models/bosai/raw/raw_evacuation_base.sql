{# 避難拠点の生データ。data/bosai/evacuation_base.ndjson を読む。
   自治体標準オープンデータセットの様式ではなく、名称・所在地・経度・緯度の4列。 #}

{{ config(materialized='table') }}

select *
from read_json(
    'data/bosai/evacuation_base.ndjson',
    format='newline_delimited',
    columns={
        'name': 'VARCHAR',
        'address': 'VARCHAR',
        'lat': 'VARCHAR',
        'lon': 'VARCHAR',
        '_extras': 'JSON',
        '_source_title': 'VARCHAR',
        '_source_url': 'VARCHAR',
        '_source_page': 'VARCHAR',
        '_fetched_at': 'VARCHAR'
    }
)
