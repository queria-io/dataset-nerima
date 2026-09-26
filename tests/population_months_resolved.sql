-- 二重の行を裏取りできない調査年月が残っていればビルドを落とす。
--
-- pipelines/population.py は、同一キーの行が2組ある調査年月を年度 ZIP の月次個別
-- ファイルと突き合わせて片方に絞る。裏が取れない月は片方を選ばずに2組のまま残す。
-- 残した行は mart の unique_key 検査でも落ちるが、そちらは「重複がある」としか
-- 言わない。どの月がなぜ残ったのかをここで名指しする。
--
-- 落ちたときは meta.source_files の unresolved_months と reason を見る。
-- 年度 ZIP を取れなかっただけなら次のビルドで解消する。
select
    dataset_id,
    unresolved_months,
    reason
from {{ ref('source_files') }}
where unresolved_months is not null
  and len(unresolved_months) > 0
