# 運用メモ

## 取り込み元の探し方

区のサイトは CKAN ではなく静的な HTML で、カタログ API がありません。一覧
`131202_open_data_list.csv` は42列の標準様式で出ていますが、ファイル_タイトル・
ファイル_アクセスURL・ファイル_ダウンロードURL・ファイル_サイズは64行すべて空なので、
一覧から実ファイルには到達できません。そのため各データセットのページを開き、置かれている
添付ファイルの中からファイル名の正規表現で対象を選んでいます（`nerima_datasets.yml`）。
人口のまとめ CSV はファイル名が収録期間を含んでいて毎月変わるため、URL を直接持ちません。

## ビルドを止める検査

取得に失敗した系列があるとビルドが落ちます（`tests/source_files_ingested.sql`）。
失敗時にパイプラインは空の NDJSON を書いて次へ進むので、この検査が無いと 0 行の
テーブルがそのまま公開されてしまいます。0 行のモデルには `not_null` も `unique` も
通り、座標の検査は分母 0 で素通りするため、他のテストでは止まりません。

## 2018年10〜12月の二重の行の裏取り

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

## ジオコーディングのキャッシュ

ジオコーディングの結果は `geocode_cache.ndjson` にコミットしてあり、ビルドはそれを読みます。
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

`evacuation_base` の所在地には「東京都練馬区」が付かないため、ジオコーディングの入力では前置します。

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

