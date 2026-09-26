{# 複数列の組み合わせが一意であることを確かめる。

   dbt 組み込みの unique は単一列しか見ない。複合キーが一意である前提で集計する
   モデルがあるとき、その前提が崩れると件数が黙って倍になる。 #}

{% test unique_key(model, columns) %}

select
    {{ columns | join(', ') }},
    count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
