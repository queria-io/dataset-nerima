{# 総括表のステージング。調査年月を DATE に、数値を BIGINT にする。 #}

select
    {{ ods_date('survey_month') }} as survey_month,
    item,
    nullif(category, '') as category,
    try_cast(replace(value, ',', '') as bigint) as value,
    unit,
    _source_url as source_url,
    _source_page as source_page
from {{ ref('raw_summary') }}
