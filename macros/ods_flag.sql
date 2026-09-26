{# 統制語彙のフラグ列を BOOLEAN に正規化する。
   1/○/有 = true、0/×/無 = false、それ以外（空欄含む）= NULL。 #}

{% macro ods_flag(column) -%}
case
    when {{ column }} in ('1', '○', '〇', '有') then true
    when {{ column }} in ('0', '×', '無') then false
end
{%- endmacro %}
