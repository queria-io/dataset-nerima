{# 日付列を DATE に正規化する。
   練馬区の CSV は YYYY-MM-DD と YYYY/M/D が混在する。前者は try_cast が受け、
   後者は DuckDB の既定書式で解釈できる。どちらでも解釈できない値（和暦・
   「4月頃」のような自由記述）は推測せず NULL にする。 #}

{% macro ods_date(column) -%}
coalesce(
    try_cast({{ column }} as date),
    try_strptime({{ column }}, '%Y/%m/%d')::date,
    try_strptime({{ column }}, '%Y.%m.%d')::date
)
{%- endmacro %}
