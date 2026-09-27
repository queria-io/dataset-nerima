"""防災設備の住所を ABR（アドレス・ベース・レジストリ）でジオコーディングする。

data/bosai/*.ndjson の住所を住所単位で data/geocode/addresses.ndjson に出力する。
models/bosai/raw/raw_geocode.sql がこれを読み、各 stg モデルが原典の緯度経度が無い行の
補完に使う。

防災井戸と学校防災井戸は緯度経度の列があるが全行空で、手がかりは住所しかない
（2026-09-26 時点の実測）。住所は原典のまま突き合わせられるよう、正規化はこのモジュールの
中だけで完結させ、出力には原典の住所文字列をそのまま持たせる（SQL 側に正規化を持ち込まない）。

**結果は geocode_cache.ndjson に置いてコミットする。** ABR の配布は日本国外からは取れず、
GitHub ホストランナーでは zip でないファイルが返る。毎回引きに行くと週次の更新が必ず落ちる。
施設は滅多に増えないので、キャッシュに無い住所が出たときだけ ABR を引く。引けなければ
黙って座標を落とさずにビルドを止める。キャッシュの更新は国内から回して commit する。
"""

import json
import logging
import os
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

#: ジオコーディング結果の置き場。リポジトリにコミットする
CACHE_PATH = "geocode_cache.ndjson"

#: abrg の1コマンドあたりの上限（秒）。練馬区1件の download は手元で 90 秒ほど。
#: 進まなくなったときに job の打ち切り（既定90分）まで走らせないための歯止め
ABRG_TIMEOUT = 600

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
        timeout=ABRG_TIMEOUT,
        **kwargs,
    )


def in_ci() -> bool:
    """GitHub Actions を含む CI 上かどうか。"""
    return os.environ.get("CI", "").strip().lower() in ("1", "true", "yes")


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


def load_cache(path: Path) -> dict[str, dict]:
    """コミットしてあるジオコーディング結果を 住所 → レコード で読む。"""
    if not path.exists():
        return {}
    cache: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            cache[record["address"]] = record
    return cache


def save_cache(path: Path, cache: dict[str, dict]) -> None:
    """キャッシュを住所順で書く。差分が読めるように並びを固定する。"""
    with path.open("w", encoding="utf-8") as f:
        for address in sorted(cache):
            f.write(json.dumps(cache[address], ensure_ascii=False) + "\n")


def _record(address: str, result: dict | None) -> dict:
    """abrg の結果を1行のレコードにする。採用しない粒度は座標を持たせない。

    採らなかったときも abrg が返した粒度を abr_level に残す。これが無いと、
    キャッシュを読んだだけでは「区の代表点しか返らなかった」のか
    「1件も返らなかった」のかを区別できない。
    """
    if result is None:
        return {
            "address": address,
            "geo_lat": None,
            "geo_lon": None,
            "geo_level": None,
            "abr_level": None,
        }
    level = result.get("coordinate_level") or "unknown"
    usable = level not in REJECTED_LEVELS and result.get("lat") is not None
    return {
        "address": address,
        "geo_lat": result["lat"] if usable else None,
        "geo_lon": result["lon"] if usable else None,
        "geo_level": level if usable else None,
        "abr_level": level,
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
    }


def _unreachable(missing: dict[str, str], reason: str) -> SystemExit:
    """キャッシュを更新できないときのメッセージ。直し方まで書く。"""
    sample = ", ".join(sorted(missing)[:3])
    # data/ は .gitignore に入っていて毎回取り直すので、住所を集める前に
    # bosai の取得を通す必要がある。これを書かないと手順として動かない
    fix = (
        "mise exec node@22 -- uv run python -c "
        "'from pipelines.bosai import download_bosai; "
        "from pipelines.geocode import geocode; download_bosai(); geocode()'"
    )
    return SystemExit(
        f"キャッシュに無い住所が {len(missing)} 件ある（例 {sample}）。{reason}\n"
        f"ABR の配布は日本国外からは取れないため、CI ではキャッシュを更新できない。"
        f"国内から次を回して {CACHE_PATH} をコミットする:\n"
        f"  {fix}"
    )


def _resolve(missing: dict[str, str], dest: Path, *, skip_download: bool) -> dict[str, dict]:
    """キャッシュに無い住所だけ ABR に問い合わせる。取れなければ落とす。"""
    # ランナーには Node が最初から入っているので、node の有無では CI を弾けない。
    # ABR は日本国外から取れないと分かっているので、引きに行く前に止める。
    # 引きに行くと download で進まなくなり、job の打ち切りまで走ることがある
    if in_ci():
        raise _unreachable(missing, "CI では ABR を引かない。")
    node_major = _node_major()
    if node_major is None:
        raise _unreachable(missing, "node が見つからない（Node.js 22 が要る）。")
    if node_major >= 24:
        raise _unreachable(
            missing,
            f"Node.js {node_major} では依存の better-sqlite3 がビルドできない"
            "（Node.js 22 が要る）。",
        )

    abrg_dir = dest / "abrg"
    input_path = dest / "input.txt"
    raw_output = dest / "abrg_output.ndjson"
    queries = sorted(set(missing.values()))
    input_path.write_text("\n".join(queries) + "\n", encoding="utf-8")
    logger.info("  abrg へ渡す住所 %d 件", len(queries))

    try:
        if not skip_download:
            logger.info("  ABR データ取得（練馬区）")
            download_abr(abrg_dir)
        logger.info("  ジオコーディング実行")
        run_geocoder(abrg_dir, input_path, raw_output)
    except subprocess.CalledProcessError as e:
        raise _unreachable(missing, f"abr-geocoder が失敗した（exit {e.returncode}）。") from e
    except subprocess.TimeoutExpired as e:
        raise _unreachable(
            missing, f"abr-geocoder が {ABRG_TIMEOUT} 秒で終わらなかった。"
        ) from e

    results = _load_results(raw_output)
    resolved = {}
    unanswered = []
    for address, query in missing.items():
        result = results.get(normalize(query))
        if result is None:
            # abrg は入力と同じ件数を返さない。隣接する2行を連結して1クエリに
            # してしまうことがあり、連結された側は結果が返らない
            unanswered.append(query)
        resolved[address] = _record(address, result)
    if unanswered:
        logger.warning("  abrg が結果を返さなかった住所 %d 件", len(unanswered))
        for query in unanswered[:5]:
            logger.warning("    %s", query)
    return resolved


def geocode(
    bosai_dir: str = "data/bosai",
    dest_dir: str = "data/geocode",
    cache_path: str = CACHE_PATH,
    *,
    skip_download: bool = False,
) -> None:
    """防災設備の住所に座標を付けて NDJSON に出力する。

    キャッシュに無い住所が出たときだけ ABR を引く。引けないときは座標を落とさずに止める。
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    collected = collect_addresses(Path(bosai_dir))
    if not collected:
        raise SystemExit("ジオコーディング対象の住所が 1 件も無い")
    cache = load_cache(Path(cache_path))
    missing = {a: q for a, q in collected.items() if a not in cache}
    logger.info("  住所 %d 件（キャッシュ済み %d 件）", len(collected), len(collected) - len(missing))

    if missing:
        logger.info("  キャッシュに無い住所 %d 件を ABR に問い合わせる", len(missing))
        cache.update(_resolve(missing, dest, skip_download=skip_download))
        save_cache(Path(cache_path), cache)
        logger.info("  %s を更新した。コミットすること", cache_path)

    _write(dest / "addresses.ndjson", collected, cache)


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


def _write(path: Path, collected: dict[str, str], cache: dict[str, dict]) -> None:
    """いま使っている住所のぶんだけ NDJSON に書く。

    キャッシュは過去に引いた住所も持ち続けるが、出力には現行の住所だけを入れる。
    stg_geocode が住所で一意である前提を素直に保つため。
    """
    levels: Counter[str] = Counter()
    adopted = 0

    with path.open("w", encoding="utf-8") as f:
        for address in sorted(collected):
            record = cache[address]
            level = record.get("geo_level")
            levels[level or "(座標なし)"] += 1
            if record.get("geo_lat") is not None:
                adopted += 1
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    total = len(collected)
    logger.info("  座標あり %d / %d (%.1f%%)", adopted, total, 100 * adopted / total)
    for level, count in levels.most_common():
        logger.info("    %-20s %6d (%.1f%%)", level, count, 100 * count / total)

    # 座標の付かない住所はキャッシュに固定され、次からは miss にならないので
    # 引き直されない。気付けるのはここだけなので、毎回名指しで出す
    without = [a for a in sorted(collected) if cache[a].get("geo_lat") is None]
    if without:
        logger.warning("  座標の付かない住所 %d 件（%s に入ったままになる）", len(without), CACHE_PATH)
        for address in without[:5]:
            logger.warning("    %s（abrg の粒度 %s）", address, cache[address].get("abr_level"))
