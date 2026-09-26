"""練馬区オープンデータ データパイプライン。

1. population: 世帯と人口の月次時系列の取得と正規化
2. bosai:      防災設備の一覧の取得と正規化
3. geocode:    防災設備の住所のジオコーディング（bosai の後に実行する）
4. dbt:        dbt ビルド
"""

import logging

from dbt.cli.main import dbtRunner

from pipelines.bosai import download_bosai
from pipelines.geocode import geocode
from pipelines.population import download_population

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("pipelines")


def dbt_build():
    dbt = dbtRunner()
    for command in (["deps"], ["build"], ["docs", "generate"]):
        result = dbt.invoke(command)
        if not result.success:
            raise SystemExit(f"dbt {' '.join(command)} failed")


def main():
    logger.info("1/4: population (世帯と人口)")
    download_population()

    logger.info("2/4: bosai (防災設備)")
    download_bosai()

    logger.info("3/4: geocode (住所のジオコーディング)")
    geocode()

    logger.info("4/4: dbt build")
    dbt_build()


if __name__ == "__main__":
    main()
