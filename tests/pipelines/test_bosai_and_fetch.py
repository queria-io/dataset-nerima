"""防災設備の列マッピングと、ページからファイルを選ぶところ。

列マッピングは先勝ちで、どの標準キーにも当たらない見出しは _extras へ退避する。
取りこぼすと mart の列が黙って NULL になるだけで、どのテストにも引っかからない。
"""

import pytest

from pipelines import bosai as B
from pipelines import fetch as F


class TestNormalize:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("﻿全国地方公共団体コード", "全国地方公共団体コード"),
            ("人口（男）[人]", "人口(男)[人]"),
            ("建物名等（方書）", "建物名等(方書)"),
            (" 名称 ", "名称"),
            ('"名称"', "名称"),
        ],
    )
    def test_header(self, value, expected):
        assert F.normalize_header(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("総 数", "総数"), ("370,647", "370647"), ("旭丘１丁目", "旭丘1丁目"), ("", "")],
    )
    def test_value(self, value, expected):
        assert F.normalize_value(value) == expected


class TestPageFiles:
    HTML = """
    <a href="x.files/131202_care_service.csv">介護サービス事業所一覧（CSV）</a>
    <a href="x.files/131202_care_service.xlsx">同（Excel）</a>
    <a href="/kusei/tokei/opendata/index.files/riyoukiyaku.pdf">利用規約</a>
    <a href="../other.html">別のページ</a>
    <a href="x.files/2018chouchoubetu.zip">平成30年度</a>
    """
    PAGE = "https://www.city.nerima.tokyo.jp/kusei/tokei/opendata/opendatasite/a/b.html"

    def test_collects_attachments_with_absolute_urls(self):
        """どのページにも貼ってある利用規約 PDF は拾わない。データの添付ではない。"""
        files = F.page_files(self.PAGE, self.HTML)
        names = [name for name, _url, _label in files]
        assert names == [
            "131202_care_service.csv",
            "131202_care_service.xlsx",
            "2018chouchoubetu.zip",
        ]
        assert files[0][1].endswith("/opendatasite/a/x.files/131202_care_service.csv")
        assert files[0][2] == "介護サービス事業所一覧（CSV）"

    def test_find_file_matches_the_whole_name(self):
        files = F.page_files(self.PAGE, self.HTML)
        assert F.find_file(files, r"131202_care_service\.csv")[0] == "131202_care_service.csv"
        # 部分一致で拡張子違いを拾わないこと
        assert F.find_file(files, r"131202_care_service") is None
        assert F.find_file(files, r"(\d{4})chouchoubetu\.zip")[0] == "2018chouchoubetu.zip"


class TestBosaiRows:
    HEADER_MAP = F.build_header_map([
        {"key": "municipality_code", "source": ["全国地方公共団体コード"]},
        {"key": "municipality_name", "source": ["地方公共団体名"]},
        {"key": "name", "source": ["名称"]},
        {"key": "address", "source": ["所在地_連結表記", "住所"]},
        {"key": "for_earthquake", "source": ["災害種別_地震"]},
    ])

    def test_maps_headers_and_keeps_unmapped_columns(self):
        rows = [
            ["全国地方公共団体コード", "名称", "所在地_連結表記", "市区町村コード", "災害種別_地震"],
            ["131202", "練馬文化センター", "東京都練馬区練馬1-17-37", "131202", "1"],
        ]
        records, mapped = B._normalize_rows(rows, self.HEADER_MAP)
        assert records[0]["name"] == "練馬文化センター"
        assert records[0]["for_earthquake"] == "1"
        assert records[0]["_extras"] == {"市区町村コード": "131202"}
        assert "address" in mapped

    def test_first_matching_header_wins(self):
        rows = [
            ["名称", "所在地_連結表記", "住所"],
            ["A", "東京都練馬区1-1", "練馬区1-1"],
        ]
        records, _ = B._normalize_rows(rows, self.HEADER_MAP)
        assert records[0]["address"] == "東京都練馬区1-1"
        assert records[0]["_extras"] == {"住所": "練馬区1-1"}

    def test_drops_rows_without_a_name(self):
        rows = [["名称", "所在地_連結表記"], ["A", "x"], ["", "この表は…"]]
        records, _ = B._normalize_rows(rows, self.HEADER_MAP)
        assert [r["name"] for r in records] == ["A"]

    def test_returns_none_when_no_header_row_is_found(self):
        records, mapped = B._normalize_rows([["1", "2"], ["3", "4"]], self.HEADER_MAP)
        assert records is None
        assert mapped == []
