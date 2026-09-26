{# 世帯と人口（町丁目別）の生データ。data/population/by_town.ndjson を読む。 #}

{{ config(materialized='table') }}

select *
from read_json(
    'data/population/by_town.ndjson',
    format='newline_delimited',
    columns={
        'survey_month': 'VARCHAR',
        'town': 'VARCHAR',
        'area_level': 'VARCHAR',
        'town_name': 'VARCHAR',
        'chome': 'VARCHAR',
        'households': 'VARCHAR',
        'male': 'VARCHAR',
        'female': 'VARCHAR',
        'total': 'VARCHAR',
        '_source_url': 'VARCHAR',
        '_source_page': 'VARCHAR',
        '_fetched_at': 'VARCHAR'
    }
)
