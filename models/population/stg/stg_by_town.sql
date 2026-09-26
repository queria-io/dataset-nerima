{# 町丁目別のステージング。調査年月を DATE に、世帯数と人口を BIGINT にする。
   丁目は原典が全角数字なので文字列のまま残し、整数として使える値だけ chome_number に入れる。 #}

select
    {{ ods_date('survey_month') }} as survey_month,
    town,
    area_level,
    nullif(town_name, '') as town_name,
    nullif(chome, '') as chome,
    try_cast(translate(chome, '０１２３４５６７８９', '0123456789') as integer) as chome_number,
    try_cast(replace(households, ',', '') as bigint) as households,
    try_cast(replace(male, ',', '') as bigint) as male,
    try_cast(replace(female, ',', '') as bigint) as female,
    try_cast(replace(total, ',', '') as bigint) as total,
    _source_url as source_url,
    _source_page as source_page
from {{ ref('raw_by_town') }}
