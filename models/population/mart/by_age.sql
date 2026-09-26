-- 世帯と人口（年齢別）。1行 = 調査年月 × 年齢 × 性別。総計行を含む（is_total で分ける）
select
    survey_month,
    age,
    age_years,
    is_total,
    sex,
    value,
    unit,
    source_url,
    source_page
from {{ ref('stg_by_age') }}
