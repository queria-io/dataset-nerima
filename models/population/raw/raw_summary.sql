{# 世帯と人口（総括表）の生データ。
   pipelines/population.py が練馬区公開のまとめ CSV を取り込み、
   2018年10〜12月の二重の行を月次個別ファイルで裏取りしてから data/population/summary.ndjson に保存する。 #}

{{ config(materialized='table') }}

select *
from read_json(
    'data/population/summary.ndjson',
    format='newline_delimited',
    columns={
        'survey_month': 'VARCHAR',
        'item': 'VARCHAR',
        'category': 'VARCHAR',
        'value': 'VARCHAR',
        'unit': 'VARCHAR',
        '_source_url': 'VARCHAR',
        '_source_page': 'VARCHAR',
        '_fetched_at': 'VARCHAR'
    }
)
