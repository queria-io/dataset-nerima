{# 世帯と人口（年齢別）の生データ。data/population/by_age.ndjson を読む。 #}

{{ config(materialized='table') }}

select *
from read_json(
    'data/population/by_age.ndjson',
    format='newline_delimited',
    columns={
        'survey_month': 'VARCHAR',
        'age': 'VARCHAR',
        'sex': 'VARCHAR',
        'value': 'VARCHAR',
        'unit': 'VARCHAR',
        '_source_url': 'VARCHAR',
        '_source_page': 'VARCHAR',
        '_fetched_at': 'VARCHAR'
    }
)
