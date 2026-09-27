# dataset-nerima

東京都練馬区がオープンデータサイトで公開しているデータを、Queria のカタログ
（[data.queria.io](https://data.queria.io/)）へ取り込むデータセットです。

## データ出典

[練馬区オープンデータサイト](https://www.city.nerima.tokyo.jp/kusei/tokei/opendata/opendatasite/index.html)
が公開している CSV を収録しています。ライセンスは
[練馬区オープンデータ利用規約](https://www.city.nerima.tokyo.jp/kusei/tokei/opendata/index.files/riyoukiyaku.pdf)
に定める CC BY 4.0 で、商用利用も認められています。

区が公開している64データセットのうち、東京都オープンデータカタログサイト経由で取れる
14種別は [`metro_tokyo`](https://github.com/queria-io/dataset-metro-tokyo) の `ods` スキーマに
入っているため、ここでは収録しません。区の AED・公共施設・公園トイレ・指定緊急避難場所などは
`metro_tokyo.ods.*` にあります。

区のサイトは CKAN ではなく静的な HTML で、カタログ API がありません。一覧
`131202_open_data_list.csv` は42列の標準様式で出ていますが、ファイル_タイトル・
ファイル_アクセスURL・ファイル_ダウンロードURL・ファイル_サイズは64行すべて空なので、
一覧から実ファイルには到達できません。そのため各データセットのページを開き、置かれている
添付ファイルの中からファイル名の正規表現で対象を選んでいます（`nerima_datasets.yml`）。
人口のまとめ CSV はファイル名が収録期間を含んでいて毎月変わるため、URL を直接持ちません。

## 収録テーブル

| テーブル | 内容 | 行数 | 収録期間 |
| --- | --- | ---: | --- |
| `population.by_age` | 世帯と人口（年齢別、1歳刻み） | 35,203 | 2017-04 〜 2026-09（110か月） |
| `population.by_town` | 世帯と人口（町丁目別） | 30,135 | 2016-04 〜 2026-09（123か月） |
| `population.summary` | 世帯と人口（総括表） | 1,230 | 2016-04 〜 2026-09（123か月） |
| `bosai.disaster_well` | 防災井戸（民間 + 学校） | 125 | — |
| `bosai.evacuation_base` | 避難拠点 | 98 | — |
| `bosai.homecoming_support_station` | 帰宅支援ステーション | 7 | — |
| `bosai.emergency_water_station` | 災害時給水ステーション | 5 | — |
| `meta.source_files` | 取り込みの実行結果 | 8 | — |

行数は 2026-09-26 時点の実測です。防災設備の行数が少ないのは取り込みの欠落ではなく、
原典の CSV がその件数で公開されているためです。テーブルの中身が少ないときは
`meta.source_files` の `status` と `row_count` を見ると、原典がそうなのか取り込みで
落ちたのかを切り分けられます。

取得に失敗した系列があるとビルドが落ちます（`tests/source_files_ingested.sql`）。
失敗時にパイプラインは空の NDJSON を書いて次へ進むので、この検査が無いと 0 行の
テーブルがそのまま公開されてしまいます。0 行のモデルには `not_null` も `unique` も
通り、座標の検査は分母 0 で素通りするため、他のテストでは止まりません。

## 原典に無い月

収録期間の中に、原典のまとめ CSV が行を持たない月があります。取り込みで落としたものでは
ありません。

- 3表とも 2021年10月・11月・12月がありません
- `by_age` はさらに 2024年6月がありません

月次の推移を出すときは、日付の連続を前提にせず実際にある月で組みます。

## 世帯と人口の集計行

3表とも集計行を含みます。

- `by_town` は `area_level` が `総数`（区全体）/ `町域計`（町ごとの合計）/ `丁目`
- `by_age` は `is_total` が総計の行で true。年齢不詳の行もあります
- `summary` は `item` が 世帯数 / 総人口 / 日本人の人口 / 外国人の人口、`category` が 男 / 女 / 計

町丁目だけを数えるなら `area_level = '丁目'`、年齢を足し上げるなら `is_total = false` で絞ります。

`by_age` の年齢の総計行のラベルは原典が「総 数」（全角空白入り）で、2026年6月だけ「総数」です。
月をまたいだ集計でラベルの分岐が要らないよう `is_total` を付けてあるので、`age` の値では
判定しないでください。2026年6月は `sex = '合計'` の行が無く、男性と女性しかありません。

## 2018年10〜12月の二重の行

区が公開している全期間まとめ CSV には、2018年10月・11月・12月に限って同一キーの行が
2組入っています（総括表・町丁目別・年齢別の3系列すべて）。値は別物で、列では区別できません。

年度 ZIP に入っている月次個別ファイルと値が一致する側だけを採っています。重複が出た
調査年月に限って ZIP を取りに行くので、上流がまとめ CSV を直せばこの経路は通らなくなります。
どの月で裏取りしたかは `meta.source_files` の `resolved_months`、落とした行数は
`dropped_rows` で引けます。

裏取りできないときは片方を選ばず、2組のまま残して `status` を `degraded` にし、
`unresolved_months` に記録します。年度 ZIP を取れない場合と、採った行が月次個別ファイルと
1対1で対応しない場合がこれに当たります。この状態になると `tests/population_months_resolved.sql`
がビルドを落とすので、**公開は前回の内容のまま据え置かれます。** `degraded` のデータが
カタログに載ることはありません。落ちたときは `meta.source_files` の `unresolved_months` と
`reason` を見ます。年度 ZIP を取れなかっただけなら次のビルドで解消します。

裏取りに年度 ZIP を使うため、上流が 2018年10〜12月の重複を直すまでは、毎回のビルドが
その取得に依存します（3系列 × 3か月）。

採った側は、収録している123か月すべてで 日本人+外国人=総人口、男+女=計、
`by_town` の総数=`summary` の総人口計 が成り立ちます。

## 座標

地図に出すときは `lat` / `lon` ではなく `geo_lat` / `geo_lon` / `geometry` を使います。
`lat` / `lon` は原典の値をそのまま残し、採用した値の由来を `geo_source` に持ちます。

原典に使える座標が無い行は、住所をデジタル庁のアドレス・ベース・レジストリで
ジオコーディングして補っています。`disaster_well` は原典が緯度経度の列を持つものの全行空で、
座標はすべてこの経路によるものです。区が座標を入れれば原典の値が優先されます。

**ジオコーディングの結果は `geocode_cache.ndjson` にコミットしてあり、ビルドはそれを読みます。**
ABR の配布は日本国外からは取れず、GitHub のホストランナーからは zip でないファイルが返ります。
毎回引きに行くと週次の更新が必ず落ちるため、キャッシュに無い住所が出たときだけ引きに行き、
引けなければ座標を落とさずにビルドを止めます。CI では引きに行く前に止めます。ランナーには
Node が最初から入っているので、ワークフローから `node_version` を外すだけでは呼ばない保証に
ならないためです。

施設が増えたときは国内から更新してコミットします。

```bash
mise exec node@22 -- uv run python -c 'from pipelines.bosai import download_bosai; from pipelines.geocode import geocode; download_bosai(); geocode()'
```

`data/` は毎回取り直すので、住所を集める前に `download_bosai()` を通します。
Node.js 22 が要ります。依存の better-sqlite3 が Node 24 でビルドできません。

座標の付かない住所があるとログに名指しで出ます。そのままコミットすると、以後は
キャッシュに当たり続けて引き直されません。

粒度は `geo_level` で引けます。原典由来は `source`、住所から求めた場合は
`residential_detail` / `residential_block` / `machiaza_detail` / `machiaza` で、
市区町村の代表点は採用しません。

`evacuation_base` は原典が名称・所在地・経度・緯度の4列で、自治体標準オープンデータセットの
様式ではありません。所在地に「東京都練馬区」が付かないため、ジオコーディングの入力では前置します。

その他の防災設備の列名は `metro_tokyo` の `ods` スキーマと揃えてあるので、同じ列名で
近隣区と並べて集計できます。

## ビルド

```bash
uv sync
bash scripts/build.sh
```

`scripts/build.sh` は `shared/scripts/build-dataset.sh` に委譲し、`queria sync` の
pull → ビルド → push を通します。target 引数は取りません。公開先は `dataset.yml` の名前、
アカウントは `QUERIA_TOKEN` で決まります。

ビルドに Node.js は要りません。座標は `geocode_cache.ndjson` から読みます。
キャッシュの更新だけが [abr-geocoder](https://github.com/digital-go-jp/abr-geocoder) を呼び、
そこでのみ Node.js 22 と国内からの実行が要ります。

公開せずに通しで確かめるときは、queria-cli の `tools/rotate.py` をスタンドインに対して回します。

```bash
uv run --group dev python tools/rotate.py \
    --repo ~/ws/ghq/github.com/queria-io/dataset-nerima -- uv run python main.py
```

個別に回す場合は `queria pull` / `queria run -- uv run python main.py` / `queria push`、
検証は `queria sql` です。`uv run dbt run` を直接実行すると DuckLake カタログと
不整合が起きるため、必ず `queria` 経由でビルドします。
