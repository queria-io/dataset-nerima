"""防災設備の一覧の取り込み。

nerima_datasets.yml の bosai に並べた種別ごとに、データセットのページから CSV を選んで
ダウンロードし、ヘッダーを標準キーに正規化して data/bosai/<id>.ndjson に出力する。
列名は metro_tokyo.ods.* と揃えてあるので、近隣区の同種別と UNION で並べられる。

同じ id を持つエントリが複数あるときは1つの NDJSON にまとめる（防災井戸と学校防災井戸は
同じ28列の様式なので、category で出どころを分けて1テーブルにする）。

データソース: 練馬区オープンデータサイト
https://www.city.nerima.tokyo.jp/kusei/tokei/opendata/opendatasite/index.html
"""

import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from pipelines.fetch import (
    Throttle,
    build_header_map,
    decode,
    fetch,
    find_file,
    normalize_header,
    page_files,
    read_rows,
)

logger = logging.getLogger("pipelines")

#: この列が空の行は実体を持たないものとして落とす（表末尾の注記行など）
IDENTITY_COLUMN = "name"

#: 種別の判定に使う必須列。取れないファイルは様式が変わったとみなして隔離する
REQUIRED_COLUMNS = ("name", "address")


def _normalize_rows(
    rows: list[list[str]], header_map: dict[str, str]
) -> tuple[list[dict] | None, list[str]]:
    """ヘッダーを標準キーにマッピングし、1行=1dict に正規化する。

    どの標準キーにもマッチしないヘッダーの値は _extras に退避する。
    標準キーは先勝ち（同じキーに複数のヘッダーがマッチしたら最初の列を採用）。
    """
    header_index = None
    for i, row in enumerate(rows[:5]):
        matches = sum(1 for cell in row if normalize_header(cell) in header_map)
        if matches >= 2:
            header_index = i
            break
    if header_index is None:
        return None, []

    key_at: dict[int, str] = {}
    extra_at: dict[int, str] = {}
    mapped: set[str] = set()
    for i, cell in enumerate(rows[header_index]):
        normalized = normalize_header(cell)
        key = header_map.get(normalized)
        if key and key not in mapped:
            key_at[i] = key
            mapped.add(key)
        elif normalized:
            extra_at[i] = normalized

    records = []
    for row in rows[header_index + 1 :]:
        record: dict = {}
        extras: dict = {}
        for i, cell in enumerate(row):
            value = cell.strip()
            if not value:
                continue
            if i in key_at:
                record[key_at[i]] = value
            elif i in extra_at:
                extras[extra_at[i]] = value
        if not record.get(IDENTITY_COLUMN):
            continue
        if extras:
            record["_extras"] = extras
        records.append(record)
    return records, sorted(mapped)


def download_bosai(
    config_path: str = "nerima_datasets.yml", dest_dir: str = "data/bosai"
) -> None:
    """防災設備の CSV を取得して種別ごとの NDJSON に正規化する。

    失敗は1エントリ単位で隔離し、source_files.ndjson に理由を記録して続行する。
    """
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    base = config["base_url"]
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    throttle = Throttle()
    fetched_at = datetime.now(UTC).isoformat()
    source_files: list[dict] = []
    by_id: dict[str, list[dict]] = defaultdict(list)

    for entry in config["bosai"]:
        page_url = base + entry["page"]
        header_map = build_header_map(
            [*entry["columns"], *entry.get("extra_columns", [])]
        )
        record = {
            "dataset_id": entry["id"],
            "dataset_title": entry["title"],
            "page": page_url,
            "category": entry.get("category"),
            "fetched_at": fetched_at,
        }

        try:
            page_html, _ = decode(fetch(page_url, throttle))
        except Exception as e:
            logger.info("  failed: %s (ページを取れない: %s)", entry["title"], e)
            source_files.append({**record, "status": "failed", "reason": f"page_error: {e}"})
            continue

        found = find_file(page_files(page_url, page_html), entry["file_pattern"])
        if found is None:
            logger.info("  skipped: %s (CSV が見つからない)", entry["title"])
            source_files.append({
                **record,
                "status": "skipped",
                "reason": f"file_not_found: {entry['file_pattern']}",
            })
            continue
        _name, url, label = found
        record.update({"url": url, "file_label": label})

        try:
            data = fetch(url, throttle)
        except Exception as e:
            logger.info("  failed: %s (%s)", entry["title"], e)
            source_files.append({**record, "status": "failed", "reason": f"fetch_error: {e}"})
            continue

        rows, encoding = read_rows(data)
        records, mapped = _normalize_rows(rows, header_map)
        if records is None:
            logger.info("  skipped: %s (ヘッダーが見つからない)", entry["title"])
            source_files.append({
                **record,
                "status": "skipped",
                "reason": "header_mismatch",
                "encoding": encoding,
            })
            continue

        missing = [name for name in REQUIRED_COLUMNS if name not in mapped]
        if missing:
            logger.info("  skipped: %s (必須列が無い: %s)", entry["title"], missing)
            source_files.append({
                **record,
                "status": "skipped",
                "reason": f"required_columns_missing: {missing}",
                "encoding": encoding,
            })
            continue

        for row in records:
            if entry.get("category"):
                row["category"] = entry["category"]
            row["_source_title"] = entry["title"]
            row["_source_url"] = url
            row["_source_page"] = page_url
            row["_fetched_at"] = fetched_at
        by_id[entry["id"]].extend(records)

        source_files.append({
            **record,
            "status": "ok",
            "encoding": encoding,
            "row_count": len(records),
        })
        logger.info("  %s: %d 行", entry["title"], len(records))

    for dataset_id in {entry["id"] for entry in config["bosai"]}:
        with (dest / f"{dataset_id}.ndjson").open("w", encoding="utf-8") as writer:
            for row in by_id.get(dataset_id, []):
                writer.write(json.dumps(row, ensure_ascii=False) + "\n")

    with (dest / "source_files.ndjson").open("w", encoding="utf-8") as writer:
        for row in source_files:
            writer.write(json.dumps(row, ensure_ascii=False) + "\n")
