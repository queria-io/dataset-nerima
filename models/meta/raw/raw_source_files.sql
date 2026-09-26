{# 取り込みの実行結果。population と bosai のパイプラインが書いた2本の NDJSON をまとめる。
   1ファイルの失敗で全体を止めないため、成功も失敗もここに残る。 #}

{{ config(materialized='table') }}

with population as (
    select
        'population' as schema_name,
        dataset_id,
        dataset_title,
        null as category,
        status,
        reason,
        encoding,
        row_count,
        dropped_rows,
        resolved_months,
        unresolved_months,
        file_label,
        url,
        page,
        fetched_at
    from read_json(
        'data/population/source_files.ndjson',
        format='newline_delimited',
        columns={
            'dataset_id': 'VARCHAR',
            'dataset_title': 'VARCHAR',
            'status': 'VARCHAR',
            'reason': 'VARCHAR',
            'encoding': 'VARCHAR',
            'row_count': 'BIGINT',
            'dropped_rows': 'BIGINT',
            'resolved_months': 'VARCHAR[]',
            'unresolved_months': 'VARCHAR[]',
            'file_label': 'VARCHAR',
            'url': 'VARCHAR',
            'page': 'VARCHAR',
            'fetched_at': 'VARCHAR'
        }
    )
),
bosai as (
    select
        'bosai' as schema_name,
        dataset_id,
        dataset_title,
        category,
        status,
        reason,
        encoding,
        row_count,
        null as dropped_rows,
        null as resolved_months,
        null as unresolved_months,
        file_label,
        url,
        page,
        fetched_at
    from read_json(
        'data/bosai/source_files.ndjson',
        format='newline_delimited',
        columns={
            'dataset_id': 'VARCHAR',
            'dataset_title': 'VARCHAR',
            'category': 'VARCHAR',
            'status': 'VARCHAR',
            'reason': 'VARCHAR',
            'encoding': 'VARCHAR',
            'row_count': 'BIGINT',
            'file_label': 'VARCHAR',
            'url': 'VARCHAR',
            'page': 'VARCHAR',
            'fetched_at': 'VARCHAR'
        }
    )
)
select * from population
union all
select * from bosai
