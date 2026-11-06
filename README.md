# 練馬区

東京都練馬区がオープンデータサイトで公開している、住民基本台帳による世帯と人口の月次の値（総括表・町丁目別・年齢別）と、災害時に使える設備（避難拠点・帰宅支援ステーション・災害時給水ステーション・防災井戸）の一覧を、SQL で検索・集計できるテーブルにしたデータセットです。

## 出典と利用条件

- [練馬区オープンデータサイト](https://www.city.nerima.tokyo.jp/kusei/tokei/opendata/opendatasite/index.html)が公開している CSV を加工して作成しています
- [練馬区オープンデータ利用規約](https://www.city.nerima.tokyo.jp/kusei/tokei/opendata/index.files/riyoukiyaku.pdf)に定める CC BY 4.0 に従います。商用利用もできます
- 区が公開しているデータセットのうち、東京都オープンデータカタログ経由で取得できる 14 種類は metro_tokyo の `ods` スキーマに入っているので、ここには収録していません。区の AED・公共施設・公園トイレ・指定緊急避難場所などは `metro_tokyo.ods.*` にあります

## テーブル

| テーブル | 内容 | 行数 | 収録期間 |
| --- | --- | ---: | --- |
| `population.by_age` | 世帯と人口（年齢別、1歳刻み） | 35,203 | 2017-04 〜 |
| `population.by_town` | 世帯と人口（町丁目別） | 30,135 | 2016-04 〜 |
| `population.summary` | 世帯と人口（総括表） | 1,230 | 2016-04 〜 |
| `bosai.disaster_well` | 防災井戸（民間 + 学校） | 125 | — |
| `bosai.evacuation_base` | 避難拠点 | 98 | — |
| `bosai.homecoming_support_station` | 帰宅支援ステーション | 7 | — |
| `bosai.emergency_water_station` | 災害時給水ステーション | 5 | — |
| `meta.source_files` | 取り込みの実行結果 | 8 | — |

行数は 2026-09-26 時点です。防災設備の行数が少ないのは、原典の CSV がその件数で公開されているためです。テーブルの行が少ないときは、`meta.source_files` の `status` と `row_count` で原典の件数なのか取り込みの失敗なのかを確認できます。

## 使い方

区の総人口の推移を出す:

```sql
SELECT survey_month, value AS population
FROM nerima.population.summary
WHERE item = '総人口' AND category = '計'
ORDER BY survey_month;
```

最新の月の、人口の多い町丁目を出す:

```sql
SELECT town_name, chome, total
FROM nerima.population.by_town
WHERE area_level = '丁目'
  AND survey_month = (SELECT max(survey_month) FROM nerima.population.by_town)
ORDER BY total DESC
LIMIT 10;
```

## 原典に無い月

収録期間の中に、原典のまとめ CSV が行を持たない月があります。月次の推移を出すときは、日付が連続していることを前提にしないでください。

- 3 つのテーブルとも 2021 年 10 月・11 月・12 月がありません
- `by_age` は 2024 年 6 月もありません

## 世帯と人口の集計行

3 つのテーブルとも集計行を含みます。

- `by_town` は `area_level` が `総数`（区全体）／`町域計`（町ごとの合計）／`丁目` です。町丁目だけを数えるときは `area_level = '丁目'` で絞ってください
- `by_age` は総計の行で `is_total` が true です。年齢不詳の行もあります。年齢を足すときは `is_total = false` で絞ってください
- `summary` は `item` が世帯数／総人口／日本人の人口／外国人の人口、`category` が男／女／計です
- `by_age` の総計の行のラベルは、原典の表記が月によって違います（「総 数」と「総数」）。`age` の値ではなく `is_total` で判定してください
- `by_age` の 2026 年 6 月は `sex = '合計'` の行が無く、男性と女性だけです

## 2018 年 10〜12 月の値

区が公開している全期間のまとめ CSV には、2018 年 10 月・11 月・12 月に限って同じキーの行が 2 組入っています。このデータセットでは、年度ごとの月次ファイルと値が一致する側だけを採っています。採った側は、収録しているすべての月で 日本人 + 外国人 = 総人口、男 + 女 = 計、`by_town` の総数 = `summary` の総人口の計 が成り立ちます。

## 座標

- 地図に表示するときは、`lat`・`lon` ではなく `geo_lat`・`geo_lon`・`geometry` を使ってください。`lat`・`lon` は原典の値のままで、採用した値の由来は `geo_source` にあります
- 原典に使える座標が無い行は、住所をデジタル庁のアドレス・ベース・レジストリでジオコーディングして補っています。`disaster_well` は原典の緯度経度が全行空なので、座標はすべて住所から求めた値です
- 座標の粒度は `geo_level` にあります。原典由来は `source`、住所から求めた値は `residential_detail`／`residential_block`／`machiaza_detail`／`machiaza` です。市区町村の代表点は採用していません
- `evacuation_base` の所在地は「東京都練馬区」を含みません
- 防災設備の列名は `metro_tokyo` の `ods` スキーマと合わせているので、近隣区と並べて集計できます

## 更新

```bash
uv sync
bash scripts/build.sh
```
