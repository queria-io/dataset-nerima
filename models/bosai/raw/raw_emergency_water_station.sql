{# 災害時給水ステーションの生データ。data/bosai/emergency_water_station.ndjson を読む。 #}

{{ config(materialized='table') }}

select *
from read_json(
    'data/bosai/emergency_water_station.ndjson',
    format='newline_delimited',
    columns={
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
        'water_type_purification': 'VARCHAR',
        'water_type_emergency_tank': 'VARCHAR',
        'water_type_small_tank': 'VARCHAR',
        'secured_volume': 'VARCHAR',
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
