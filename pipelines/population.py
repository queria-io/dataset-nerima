"""世帯と人口の月次時系列の取り込み。

練馬区は3系列（総括表・町丁目別・年齢別）のそれぞれについて、全期間をまとめた CSV を
1本置いている。月次の個別ファイルを継ぎ足す必要がないので、まとめ CSV だけを読む。

まとめ CSV には 2018年10月・11月・12月に限って同一キーの行が2組入っている（3系列すべて）。
値は別物で、どの列にも区別する手がかりが無い。年度 ZIP に入っている月次個別ファイルと
値が一致する側だけを採る。重複が出た調査年月に限って ZIP を取りに行くので、上流が
まとめ CSV を直せばこの経路は通らなくなる。

データソース: 練馬区オープンデータサイト
https://www.city.nerima.tokyo.jp/kusei/tokei/opendata/opendatasite/index.html
"""

import io
import json
import logging
import re
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from pipelines.fetch import (
    Throttle,
    decode,
    fetch,
    find_file,
    normalize_header,
    normalize_value,
    page_files,
    read_rows,
)

logger = logging.getLogger("pipelines")


def _tuple_of(row: dict, fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(normalize_value(row.get(field) or "") for field in fields)


def _header_index(rows: list[list[str]], required: str) -> int | None:
    for i, row in enumerate(rows[:5]):
        if any(normalize_header(cell) == required for cell in row):
            return i
    return None


def _monthly_summary(rows: list[list[str]]) -> set[tuple]:
    """総括表の月次個別ファイル。ヘッダー行が無く 統計項目・区分・数値・単位 の4列。"""
    parsed = set()
    for row in rows:
        if len(row) < 3 or not row[0].strip():
            continue
        value = normalize_value(row[2])
        if not re.fullmatch(r"-?\d+", value):
            continue
        parsed.add(((normalize_value(row[0]), normalize_value(row[1])), (value,)))
    return parsed


def _monthly_by_town(rows: list[list[str]]) -> set[tuple]:
    """町丁目別の月次個別ファイル。町丁目・世帯数・人口（男）・人口（女）・計の5列。"""
    index = _header_index(rows, "町丁目")
    if index is None:
        return set()
    header = [normalize_header(cell) for cell in rows[index]]
    want = ["町丁目", "世帯数[世帯]", "人口(男)[人]", "人口(女)[人]", "計[人]"]
    if any(name not in header for name in want):
        return set()
    at = {name: header.index(name) for name in want}
    parsed = set()
    for row in rows[index + 1 :]:
        if len(row) <= max(at.values()) or not row[at["町丁目"]].strip():
            continue
        parsed.add((
            (normalize_value(row[at["町丁目"]]),),
            tuple(normalize_value(row[at[name]]) for name in want[1:]),
        ))
    return parsed


def _monthly_by_age(rows: list[list[str]]) -> set[tuple]:
    """年齢別の月次個別ファイル。年齢×（合計・男性・女性）の横持ちを縦に開く。"""
    index = _header_index(rows, "年齢[歳]")
    if index is None:
        return set()
    header = [normalize_header(cell) for cell in rows[index]]
    by_sex = {"合計": "合計[人]", "男性": "男性合計[人]", "女性": "女性合計[人]"}
    if any(name not in header for name in by_sex.values()):
        return set()
    age_at = header.index("年齢[歳]")
    at = {sex: header.index(name) for sex, name in by_sex.items()}
    parsed = set()
    for row in rows[index + 1 :]:
        if len(row) <= max([age_at, *at.values()]) or not row[age_at].strip():
            continue
        age = normalize_value(row[age_at])
        for sex, position in at.items():
            parsed.add(((age, normalize_value(sex)), (normalize_value(row[position]),)))
    return parsed


#: 系列ごとの様式。out は まとめ CSV のヘッダー名 → 出力キー。
#: key は調査年月の中で一意になるべき出力キー、value は月次個別ファイルと突き合わせる出力キー。
SHAPES: dict[str, dict] = {
    "summary": {
        "out": {
            "調査年月": "survey_month",
            "統計項目": "item",
            "区分": "category",
            "数値": "value",
            "単位": "unit",
        },
        "key": ("item", "category"),
        "value": ("value",),
        "monthly": _monthly_summary,
    },
    "by_town": {
        "out": {
            "調査年月": "survey_month",
            "町丁目": "town",
            "地域階層": "area_level",
            "町名": "town_name",
            "丁目": "chome",
            "世帯数[世帯]": "households",
            "人口（男）[人]": "male",
            "人口（女）[人]": "female",
            "計[人]": "total",
        },
        "key": ("town",),
        "value": ("households", "male", "female", "total"),
        "monthly": _monthly_by_town,
    },
    "by_age": {
        "out": {
            "調査年月": "survey_month",
            "年齢": "age",
            "性別": "sex",
            "数値": "value",
            "単位": "unit",
        },
        "key": ("age", "sex"),
        "value": ("value",),
        "monthly": _monthly_by_age,
    },
}


def _fiscal_year(year_month: str) -> int:
    """YYYYMM の年度を返す（4月始まり）。"""
    year, month = int(year_month[:4]), int(year_month[4:6])
    return year if month >= 4 else year - 1


def _year_month(survey_month: str) -> str | None:
    """調査年月の文字列から YYYYMM を取り出す。"""
    match = re.match(r"(\d{4})\D(\d{1,2})\D", survey_month or "")
    if match is None:
        return None
    return f"{int(match.group(1)):04d}{int(match.group(2)):02d}"


def _read_main(data: bytes, shape: dict) -> tuple[list[dict] | None, str]:
    """まとめ CSV を出力キーの dict 列にする。様式が合わなければ None。"""
    rows, encoding = read_rows(data)
    if not rows:
        return None, encoding
    header = [normalize_header(cell) for cell in rows[0]]
    at: dict[str, int] = {}
    for source, key in shape["out"].items():
        normalized = normalize_header(source)
        if normalized not in header:
            return None, encoding
        at[key] = header.index(normalized)
    records = []
    for row in rows[1:]:
        if len(row) <= max(at.values()) or not any(cell.strip() for cell in row):
            continue
        records.append({key: row[position].strip() for key, position in at.items()})
    return records, encoding


def _monthly_from_archive(
    entry: dict, files: list, year_month: str, throttle: Throttle
) -> set[tuple] | None:
    """年度 ZIP から1か月分の個別ファイルを読み、突き合わせ用の集合にする。"""
    archive = None
    pattern = re.compile(entry["archive_pattern"] + r"\Z")
    for name, url, _label in files:
        match = pattern.match(name)
        if match and int(match.group(1)) == _fiscal_year(year_month):
            archive = url
            break
    if archive is None:
        return None
    try:
        blob = fetch(archive, throttle)
    except Exception as e:
        logger.warning("    年度 ZIP を取れない: %s (%s)", archive, e)
        return None
    member_pattern = re.compile(entry["monthly_pattern"] + r"\Z")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            base = name.rsplit("/", 1)[-1]
            match = member_pattern.match(base)
            if match and match.group(1) == year_month:
                rows, _ = read_rows(zf.read(name))
                return SHAPES[entry["shape"]]["monthly"](rows)
    return None


def _resolve_duplicates(
    entry: dict, records: list[dict], files: list, throttle: Throttle
) -> tuple[list[dict], list[str], list[str]]:
    """同一キーの行が2組ある調査年月を月次個別ファイルで裏取りして片方に絞る。

    戻り値は (採った行, 裏取りできた調査年月, できなかった調査年月)。
    できなかった月は原典のまま残す。黙って片方を選ぶと、根拠の無い値がそのまま
    公開されてしまうため。
    """
    shape = SHAPES[entry["shape"]]
    by_month: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_month[record["survey_month"]].append(record)

    resolved: list[str] = []
    unresolved: list[str] = []
    kept: list[dict] = []
    for month in sorted(by_month, reverse=True):
        rows = by_month[month]
        keys = [_tuple_of(row, shape["key"]) for row in rows]
        if len(keys) == len(set(keys)):
            kept.extend(rows)
            continue

        year_month = _year_month(month)
        monthly = (
            _monthly_from_archive(entry, files, year_month, throttle)
            if year_month
            else None
        )
        if not monthly:
            unresolved.append(month)
            kept.extend(rows)
            continue

        # 2組のうち値が同じキーもある（人口0の年齢や、たまたま一致した丁目）。
        # その場合はどちらの行も月次ファイルと一致するが、値が同じなら区別する意味が
        # 無いので1行に畳む。月次ファイルはキーごとに1行しか持たないので、同じキーで
        # 値の違う行が2つ残ることはない
        picked: list[dict] = []
        seen: set[tuple] = set()
        for row in rows:
            pair = (_tuple_of(row, shape["key"]), _tuple_of(row, shape["value"]))
            if pair not in monthly or pair in seen:
                continue
            seen.add(pair)
            picked.append(row)
        picked_keys = [_tuple_of(row, shape["key"]) for row in picked]
        if not picked or len(picked_keys) != len(set(picked_keys)):
            unresolved.append(month)
            kept.extend(rows)
            continue
        if len(picked) != len(monthly):
            logger.warning(
                "    %s: 月次個別ファイルは %d 行だが %d 行しか一致しない",
                month, len(monthly), len(picked),
            )

        logger.info(
            "    %s: %d 行 → %d 行（月次個別ファイルと一致した側）",
            month, len(rows), len(picked),
        )
        resolved.append(month)
        kept.extend(picked)
    return kept, sorted(resolved), sorted(unresolved)


def download_population(
    config_path: str = "nerima_datasets.yml", dest_dir: str = "data/population"
) -> None:
    """3系列のまとめ CSV を取得して NDJSON に正規化する。

    失敗は1系列単位で隔離し、source_files.ndjson に理由を記録して続行する。
    """
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    base = config["base_url"]
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    throttle = Throttle()
    fetched_at = datetime.now(UTC).isoformat()
    source_files: list[dict] = []

    for entry in config["population"]:
        out_path = dest / f"{entry['id']}.ndjson"
        page_url = base + entry["page"]
        record = {
            "dataset_id": entry["id"],
            "dataset_title": entry["title"],
            "page": page_url,
            "fetched_at": fetched_at,
        }

        def bail(**fields) -> None:
            source_files.append({**record, **fields})
            out_path.write_text("", encoding="utf-8")

        try:
            page_html, _ = decode(fetch(page_url, throttle))
        except Exception as e:
            logger.info("  failed: %s (ページを取れない: %s)", entry["id"], e)
            bail(status="failed", reason=f"page_error: {e}")
            continue

        files = page_files(page_url, page_html)
        found = find_file(files, entry["file_pattern"])
        if found is None:
            logger.info("  skipped: %s (まとめ CSV が見つからない)", entry["id"])
            bail(status="skipped", reason=f"file_not_found: {entry['file_pattern']}")
            continue
        _name, url, label = found
        record.update({"url": url, "file_label": label})

        try:
            data = fetch(url, throttle)
        except Exception as e:
            logger.info("  failed: %s (%s)", entry["id"], e)
            bail(status="failed", reason=f"fetch_error: {e}")
            continue

        records, encoding = _read_main(data, SHAPES[entry["shape"]])
        if records is None:
            logger.info("  skipped: %s (様式が合わない)", entry["id"])
            bail(status="skipped", reason="header_mismatch", encoding=encoding)
            continue

        before = len(records)
        records, resolved, unresolved = _resolve_duplicates(entry, records, files, throttle)

        with out_path.open("w", encoding="utf-8") as writer:
            for row in records:
                row["_source_url"] = url
                row["_source_page"] = page_url
                row["_fetched_at"] = fetched_at
                writer.write(json.dumps(row, ensure_ascii=False) + "\n")

        fields: dict = {
            "status": "degraded" if unresolved else "ok",
            "encoding": encoding,
            "row_count": len(records),
            "dropped_rows": before - len(records),
            "resolved_months": resolved,
            "unresolved_months": unresolved,
        }
        if unresolved:
            fields["reason"] = f"duplicate_months_unresolved: {unresolved}"
        source_files.append({**record, **fields})

        dropped = before - len(records)
        suffix = f"（重複として {dropped} 行を落とした）" if dropped else ""
        logger.info("  %s: %d 行%s", entry["id"], len(records), suffix)
        if unresolved:
            logger.warning("  %s: 裏取りできなかった調査年月 %s", entry["id"], unresolved)

    with (dest / "source_files.ndjson").open("w", encoding="utf-8") as writer:
        for row in source_files:
            writer.write(json.dumps(row, ensure_ascii=False) + "\n")
