"""練馬区オープンデータ データパイプライン。

1. population: 世帯と人口の月次時系列の取得と正規化
2. dbt:        dbt ビルド
"""

import logging

from dbt.cli.main import dbtRunner

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
    logger.info("1/2: population (世帯と人口)")
    download_population()

    logger.info("2/2: dbt build")
    dbt_build()


if __name__ == "__main__":
    main()
