"""防災設備の住所を ABR（アドレス・ベース・レジストリ）でジオコーディングする。

data/bosai/*.ndjson の住所を abr-geocoder に通し、住所単位で
data/geocode/addresses.ndjson に出力する。models/bosai/raw/raw_geocode.sql がこれを読み、
各 stg モデルが原典の緯度経度が無い行の補完に使う。

防災井戸と学校防災井戸は緯度経度の列があるが全行空で、手がかりは住所しかない
（2026-09-26 時点の実測）。住所は原典のまま突き合わせられるよう、正規化はこのモジュールの
中だけで完結させ、出力には原典の住所文字列をそのまま持たせる（SQL 側に正規化を持ち込まない）。
"""

import json
import logging
import shutil
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

logger = logging.getLogger("pipelines")

#: 使う abr-geocoder のバージョン。上げるときは採用率を測ってから
ABRG_VERSION = "2.3.1"

#: 練馬区の全国地方公共団体コード。都道府県コードを渡すと住居表示データが落ちてこず
#: 地番マスターだけになるので、市区町村コードを明示する
NERIMA_LG_CODE = "131202"

#: 住所を持つ種別。data/bosai/<id>.ndjson を読む
GEOCODED_DATASETS = [
    "evacuation_base",
    "homecoming_support_station",
    "emergency_water_station",
    "disaster_well",
]

#: 採用しない座標の粒度。city は市区町村の代表点で、地図に出すと区役所にピンが集まるだけ。
#: prefecture も同じ理由。unknown は座標が無い
REJECTED_LEVELS = frozenset({"city", "prefecture", "unknown"})

#: 都道府県名。住所がこれで始まるなら前置はしない
PREFECTURES = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県",
    "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県",
    "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県",
    "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
)


def _clean(value: object) -> str:
    """NDJSON の値を住所として扱える文字列にする。"""
    if value is None:
        return ""
    return str(value).strip()


def normalize(text: str) -> str:
    """abr-geocoder が返す query.input と突き合わせるためのキー。

    abrg は入力を NFKC 正規化し連続空白を畳んで返すので、こちらも同じ形にする。
    生の文字列でキーにすると全角括弧を含む住所が軒並み外れる。
    """
    return " ".join(unicodedata.normalize("NFKC", text).split())


def geocode_input(address: str) -> str:
    """abrg に渡す住所。都道府県名・区名が無ければ前置する。

    避難拠点は所在地が「旭丘2-21-1」のように町字から始まるので、そのままでは
    別の自治体の町字と一致しうる。すでに都道府県名で始まる住所には何も足さない。
    区が区外に施設を持っていた場合に「東京都練馬区山梨県…」という存在しない住所を
    作らないため。
    """
    address = address.strip()
    if address.startswith(PREFECTURES):
        return address
    if address.startswith("練馬区"):
        return "東京都" + address
    return "東京都練馬区" + address


def collect_addresses(bosai_dir: Path) -> dict[str, str]:
    """防災設備の NDJSON から 原典の住所 → abrg に渡す住所 を集める。"""
    collected: dict[str, str] = {}
    for dataset_id in GEOCODED_DATASETS:
        path = bosai_dir / f"{dataset_id}.ndjson"
        if not path.exists():
            logger.warning("  %s: NDJSON が無いので飛ばす", dataset_id)
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                address = _clean(json.loads(line).get("address"))
                if address and address not in collected:
                    collected[address] = geocode_input(address)
    return collected


def _node_major() -> int | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        out = subprocess.run(
            [node, "--version"], capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    return int(out.stdout.strip().lstrip("v").split(".")[0])


def _abrg(args: list[str], **kwargs) -> None:
    """abr-geocoder を npx 経由で実行する。"""
    subprocess.run(
        ["npx", "--yes", f"@digital-go-jp/abr-geocoder@{ABRG_VERSION}", *args],
        check=True,
        **kwargs,
    )


def download_abr(abrg_dir: Path) -> None:
    """練馬区の ABR データを取得する。"""
    abrg_dir.mkdir(parents=True, exist_ok=True)
    # スレッド既定だと複数ワーカーが同じ sqlite を掴んで SQLITE_BUSY で即死するので
    # 1 に固定する
    _abrg(["download", "-c", NERIMA_LG_CODE, "-d", str(abrg_dir), "-t", "1", "--silent"])


def run_geocoder(abrg_dir: Path, input_path: Path, output_path: Path) -> None:
    """住所ファイルをジオコーディングする。

    target=residential は地番マスターを使わない指定。地番を使うと解決が地番側に
    寄って街区の解決を奪い、住居表示の採用がかえって減る。ライセンスの面でも
    登記所備付地図データ利用規約に触れずに済む。
    """
    _abrg([
        str(input_path), str(output_path),
        "-d", str(abrg_dir), "-f", "ndjson",
        "--target", "residential", "--silent",
    ])


def geocode(
    bosai_dir: str = "data/bosai",
    dest_dir: str = "data/geocode",
    *,
    skip_download: bool = False,
) -> None:
    """防災設備の住所をジオコーディングして NDJSON に出力する。"""
    node_major = _node_major()
    if node_major is None:
        raise SystemExit("node が見つからない。abr-geocoder の実行には Node.js 22 が要る")
    if node_major >= 24:
        raise SystemExit(
            f"Node.js {node_major} では abr-geocoder の依存 better-sqlite3 がビルドできない。"
            "Node.js 22 を使うこと"
        )

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    abrg_dir = dest / "abrg"
    input_path = dest / "input.txt"
    raw_output = dest / "abrg_output.ndjson"

    collected = collect_addresses(Path(bosai_dir))
    logger.info("  住所 %d 件", len(collected))
    if not collected:
        raise SystemExit("ジオコーディング対象の住所が 1 件も無い")

    queries = sorted(set(collected.values()))
    input_path.write_text("\n".join(queries) + "\n", encoding="utf-8")
    logger.info("  abrg へ渡す住所 %d 件", len(queries))

    if not skip_download:
        logger.info("  ABR データ取得（練馬区）")
        download_abr(abrg_dir)
    logger.info("  ジオコーディング実行")
    run_geocoder(abrg_dir, input_path, raw_output)

    results = _load_results(raw_output)
    _write(dest / "addresses.ndjson", collected, results)


def _load_results(path: Path) -> dict[str, dict]:
    """abrg の出力を正規化キー → 結果 に読み込む。"""
    results: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            results[normalize(record["query"]["input"])] = record["result"]
    return results


def _write(path: Path, collected: dict[str, str], results: dict[str, dict]) -> None:
    """住所単位の結果を NDJSON に書く。"""
    levels: Counter[str] = Counter()
    unresolved: list[str] = []
    adopted = 0

    with path.open("w", encoding="utf-8") as f:
        for address, query in sorted(collected.items()):
            result = results.get(normalize(query))
            if result is None:
                # abrg は入力と同じ件数を返さない。隣接する2行を連結して1クエリに
                # してしまうことがあり、連結された側は結果が返らない。黙って落とさず
                # 件数を数える
                unresolved.append(query)
                levels["(結果なし)"] += 1
                continue
            level = result.get("coordinate_level") or "unknown"
            levels[level] += 1
            usable = level not in REJECTED_LEVELS and result.get("lat") is not None
            if usable:
                adopted += 1
            f.write(json.dumps({
                "address": address,
                "geo_lat": result["lat"] if usable else None,
                "geo_lon": result["lon"] if usable else None,
                "geo_level": level if usable else None,
                "lg_code": result.get("lg_code"),
                "machiaza_id": result.get("machiaza_id"),
                "pref": result.get("pref"),
                "city": result.get("city"),
                "ward": result.get("ward"),
                "oaza_cho": result.get("oaza_cho"),
                "chome": result.get("chome"),
                "koaza": result.get("koaza"),
                "blk_num": result.get("blk_num"),
                "rsdt_num": result.get("rsdt_num"),
                "rsdt_num2": result.get("rsdt_num2"),
                "match_level": result.get("match_level"),
            }, ensure_ascii=False) + "\n")

    total = len(collected)
    logger.info("  採用 %d / %d (%.1f%%)", adopted, total, 100 * adopted / total)
    for level, count in levels.most_common():
        logger.info("    %-20s %6d (%.1f%%)", level, count, 100 * count / total)
    if unresolved:
        logger.warning("  abrg が結果を返さなかった住所 %d 件", len(unresolved))
        for query in unresolved[:5]:
            logger.warning("    %s", query)
