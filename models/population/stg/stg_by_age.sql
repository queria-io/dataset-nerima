{# 年齢別のステージング。調査年月を DATE に、人数を BIGINT にする。

   年齢の総計行のラベルは原典が「総 数」（全角空白入り）で、2026年6月だけ「総数」。
   月をまたいだ集計でラベルの分岐が要らないよう、is_total で立てる。
   年齢が整数で表されている行だけ age_years に入れる（総計行と不詳者は NULL）。 #}

select
    {{ ods_date('survey_month') }} as survey_month,
    age,
    replace(replace(age, '　', ''), ' ', '') in ('総数') as is_total,
    try_cast(replace(replace(age, '　', ''), ' ', '') as integer) as age_years,
    sex,
    try_cast(replace(value, ',', '') as bigint) as value,
    unit,
    _source_url as source_url,
    _source_page as source_page
from {{ ref('raw_by_age') }}
