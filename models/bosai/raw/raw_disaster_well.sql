{# 防災井戸の生データ。data/bosai/disaster_well.ndjson を読む。
   防災井戸と学校防災井戸は同じ28列の様式なので1ファイルにまとめてあり、
   category（民間 / 学校）で出どころを分ける。 #}

{{ config(materialized='table') }}

select *
from read_json(
    'data/bosai/disaster_well.ndjson',
    format='newline_delimited',
    columns={
        'category': 'VARCHAR',
        'municipality_code': 'VARCHAR',
        'municipality_name': 'VARCHAR',
        'address_municipality_code': 'VARCHAR',
        'facility_id': 'VARCHAR',
        'name': 'VARCHAR',
        'name_kana': 'VARCHAR',
        'name_en': 'VARCHAR',
        'town_id': 'VARCHAR',
        'address': 'VARCHAR',
        'prefecture': 'VARCHAR',
        'city': 'VARCHAR',
        'town': 'VARCHAR',
        'street_number': 'VARCHAR',
        'building_name': 'VARCHAR',
        'lat': 'VARCHAR',
        'lon': 'VARCHAR',
        'elevation': 'VARCHAR',
        'phone_number': 'VARCHAR',
        'extension': 'VARCHAR',
        'contact_email': 'VARCHAR',
        'contact_form_url': 'VARCHAR',
        'contact_note': 'VARCHAR',
        'postal_code': 'VARCHAR',
        'url': 'VARCHAR',
        'image': 'VARCHAR',
        'image_license': 'VARCHAR',
        'notes': 'VARCHAR',
        '_extras': 'JSON',
        '_source_title': 'VARCHAR',
        '_source_url': 'VARCHAR',
        '_source_page': 'VARCHAR',
        '_fetched_at': 'VARCHAR'
    }
)
