-- 世帯と人口（町丁目別）。1行 = 調査年月 × 町丁目。集計行を含む（area_level で分ける）
select
    survey_month,
    town,
    area_level,
    town_name,
    chome,
    chome_number,
    households,
    male,
    female,
    total,
    source_url,
    source_page
from {{ ref('stg_by_town') }}
