"""練馬区オープンデータサイトからファイルを取ってくる共通処理。

サイトは静的な HTML でカタログ API が無く、一覧 CSV のファイル欄も空なので、
データセットのページに置かれた添付ファイルの一覧から正規表現で対象を選ぶ。
"""

import csv
import re
import time
import unicodedata
import urllib.parse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# 素の urllib は名乗らないと 403 を返すホストがあるため、必ず UA を付ける
USER_AGENT = "dataset-nerima (+https://github.com/queria-io/dataset-nerima)"

# 同一ホストへの最小リクエスト間隔（秒）。取りに行くのは十数本なので控えめでよい
REQUEST_INTERVAL = 0.5

# 5xx / 接続断のリトライ回数
MAX_RETRIES = 2

# 添付ファイルとして扱う拡張子
FILE_EXTENSIONS = (".csv", ".xlsx", ".xls", ".zip")

_LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


class Throttle:
    """最小リクエスト間隔を保証する。"""

    def __init__(self, interval: float = REQUEST_INTERVAL):
        self._interval = interval
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last = time.monotonic()


def fetch(url: str, throttle: Throttle) -> bytes:
    """URL を取得する。5xx・接続断は指数バックオフで再試行、4xx は即失敗。"""
    for attempt in range(MAX_RETRIES + 1):
        throttle.wait()
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=60) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as e:
            status = getattr(e, "code", None)
            retryable = status is None or status >= 500
            if not retryable or attempt == MAX_RETRIES:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def decode(data: bytes) -> tuple[str, str]:
    """バイト列を (テキスト, エンコーディング名) で返す。

    練馬区はファイルによって UTF-8 BOM 付きと CP932 が混在する。まとめ CSV は
    UTF-8、防災系の一覧と年度 ZIP 内の月次個別ファイルは CP932（2026-09-26 時点）。
    CP932 は UTF-8 バイト列を誤って受理するため、必ず utf-8 を先に試す。
    """
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16"), "utf-16"
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8(replace)"


def read_rows(data: bytes) -> tuple[list[list[str]], str]:
    """CSV のバイト列を (行のリスト, エンコーディング名) にする。"""
    text, encoding = decode(data)
    return list(csv.reader(text.splitlines())), encoding


def page_files(page_url: str, html: str) -> list[tuple[str, str, str]]:
    """ページに置かれた添付ファイルを (ファイル名, 絶対URL, リンク文字列) で返す。"""
    seen: set[str] = set()
    files: list[tuple[str, str, str]] = []
    for href, label in _LINK.findall(html):
        path = href.split("?")[0]
        if not path.lower().endswith(FILE_EXTENSIONS):
            continue
        absolute = urllib.parse.urljoin(page_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        name = urllib.parse.unquote(absolute.rsplit("/", 1)[-1])
        text = re.sub(r"\s+", " ", _TAG.sub("", label)).strip()
        files.append((name, absolute, text))
    return files


def find_file(
    files: list[tuple[str, str, str]], pattern: str
) -> tuple[str, str, str] | None:
    """ファイル名が pattern に完全一致する最初の添付ファイルを返す。"""
    compiled = re.compile(pattern + r"\Z")
    for entry in files:
        if compiled.match(entry[0]):
            return entry
    return None


def normalize_header(header: str) -> str:
    """CSV ヘッダー名を照合用に正規化する（BOM・引用符・空白・改行の除去、NFKC）。"""
    text = header.replace("﻿", "").strip().strip('"').strip("'")
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", "", text)


def normalize_value(value: str) -> str:
    """値を照合用に正規化する。全角数字・空白・桁区切りの違いを畳む。"""
    text = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", "", text).replace(",", "")


def build_header_map(columns: list[dict]) -> dict[str, str]:
    """columns 定義から 正規化ヘッダー名 → 標準キー の対応を作る（先勝ち）。"""
    header_map: dict[str, str] = {}
    for column in columns:
        for source in column["source"]:
            header_map.setdefault(normalize_header(source), column["key"])
    return header_map
