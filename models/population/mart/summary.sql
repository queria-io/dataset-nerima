-- 世帯と人口（総括表）。1行 = 調査年月 × 統計項目 × 区分
select
    survey_month,
    item,
    category,
    value,
    unit,
    source_url,
    source_page
from {{ ref('stg_summary') }}
