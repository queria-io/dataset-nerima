-- 取り込みの実行結果。1行 = 取りに行ったファイル1本
select
    schema_name,
    dataset_id,
    dataset_title,
    category,
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
    try_cast(fetched_at as timestamp) as fetched_at
from {{ ref('raw_source_files') }}
