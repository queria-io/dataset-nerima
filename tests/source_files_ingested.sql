-- 取り込みが成功していないファイルがあればビルドを落とす。
--
-- 取得失敗・様式不一致・必須列欠落のとき pipelines は空の NDJSON を書いて次へ進む。
-- read_json はそれを 0 行として正常に読むので、そのままだと「30,135行のテーブルが
-- 0 行に置き換わったまま dbt build は緑」で push まで進んでしまう。0 行のモデルには
-- not_null も unique も accepted_values も通り、ods_geo_coverage と
-- ods_geocode_coverage は分母 0 の下駄で素通りする。Sync は毎週無人で走るため、
-- 上流の URL 差し替え1本で公開中のデータが消える。
--
-- ここで落とせば push の手前で止まり、前に公開した内容がそのまま残る。
-- degraded（取れてはいるが二重の行を裏取りできない月が残った）は取得の失敗ではないので
-- ここでは落とさず、population_months_resolved が理由を名指しして落とす。
select
    schema_name,
    dataset_id,
    dataset_title,
    status,
    reason,
    row_count
from {{ ref('source_files') }}
where status not in ('ok', 'degraded')
