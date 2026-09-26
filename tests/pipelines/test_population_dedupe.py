"""世帯と人口の二重の行の解決と、月次個別ファイルのパーサ。

まとめ CSV には 2018年10〜12月に限って同一キーの行が2組ある。どちらを採るかは
年度 ZIP の月次個別ファイルとの突合だけで決まるので、突合が外れたときに黙って
片方を採らないこと、黙って行を落とさないことをここで押さえる。

まとめ CSV は UTF-8 で全角の見出し、月次個別ファイルは CP932 で表記も揃っていない。
突合の両側が同じ正規化を通ることが前提なので、その対称性も確かめる。
"""

import pytest

from pipelines import population as P


def _entry(shape="by_town"):
    return {
        "id": shape,
        "title": shape,
        "page": "tokei_kusei/x.html",
        "shape": shape,
        "file_pattern": "x",
        "archive_pattern": r"(\d{4})x\.zip",
        "monthly_pattern": r"(\d{6})x\.csv",
    }


def _town_row(month, town, households, male, female, total, level="丁目"):
    return {
        "survey_month": month,
        "town": town,
        "area_level": level,
        "town_name": town,
        "chome": "",
        "households": households,
        "male": male,
        "female": female,
        "total": total,
    }


class TestYearMonth:
    def test_fiscal_year_starts_in_april(self):
        assert P._fiscal_year("201804") == 2018
        assert P._fiscal_year("201903") == 2018
        assert P._fiscal_year("201904") == 2019

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("2018-12-01", "201812"), ("2026/9/1", "202609"), ("", None), ("2018", None)],
    )
    def test_year_month(self, value, expected):
        assert P._year_month(value) == expected


class TestMonthlyParsers:
    def test_by_town_normalizes_width_and_spacing(self):
        """月次側の「総 数」と全角の見出しが、まとめ側の表記に畳まれる。"""
        rows = [
            ["町丁目", "世帯数[世帯]", "人口（男）[人]", "人口（女）[人]", "計[人]"],
            ["総 数", "370,647", "356440", "376143", "732583"],
            ["旭丘１丁目", "2500", "1200", "1300", "2500"],
        ]
        parsed = P._monthly_by_town(rows)
        assert (("総数",), ("370647", "356440", "376143", "732583")) in parsed
        assert (("旭丘1丁目",), ("2500", "1200", "1300", "2500")) in parsed

    def test_by_town_rejects_other_layouts(self):
        assert P._monthly_by_town([["町丁目", "人口"], ["旭丘", "1"]]) == set()

    def test_by_age_pivots_to_long(self):
        rows = [
            ["年齢[歳]", "合 計[人]", "男性合計[人]", "女性合計[人]"],
            ["総 数", "732583", "356440", "376143"],
            ["0", "5764", "2934", "2830"],
        ]
        parsed = P._monthly_by_age(rows)
        assert (("総数", "合計"), ("732583",)) in parsed
        assert (("0", "男性"), ("2934",)) in parsed
        assert (("0", "女性"), ("2830",)) in parsed

    def test_summary_has_no_header_and_skips_non_numeric(self):
        rows = [
            ["世帯数", "", "370647", "[世帯]"],
            ["総人口", "男", "356,440", "[人]"],
            ["注記", "", "この表は…", ""],
        ]
        parsed = P._monthly_summary(rows)
        assert (("世帯数", ""), ("370647",)) in parsed
        assert (("総人口", "男"), ("356440",)) in parsed
        assert len(parsed) == 2


class TestReadMain:
    def test_maps_full_width_headers(self):
        data = (
            "調査年月,町丁目,地域階層,町名,丁目,世帯数[世帯],"
            "人口（男）[人],人口（女）[人],計[人]\n"
            "2026-09-01,旭丘,町域計,旭丘,,5270,3851,3787,7638\n"
        ).encode("utf-8")
        records, encoding = P._read_main(data, P.SHAPES["by_town"])
        assert encoding == "utf-8-sig"
        assert records == [_town_row("2026-09-01", "旭丘", "5270", "3851", "3787", "7638", "町域計")]

    def test_returns_none_when_a_column_is_missing(self):
        data = b"\xe8\xaa\xbf\xe6\x9f\xbb\xe5\xb9\xb4\xe6\x9c\x88\n2026-09-01\n"
        records, _ = P._read_main(data, P.SHAPES["by_town"])
        assert records is None


class TestResolveDuplicates:
    """月次個別ファイルの取得は差し替える。ここで見たいのは突合の判断だけ。"""

    def _resolve(self, monkeypatch, records, monthly):
        monkeypatch.setattr(
            P, "_monthly_from_archive", lambda entry, files, ym, throttle: monthly
        )
        return P._resolve_duplicates(_entry(), records, [], P.Throttle(interval=0))

    def test_months_without_duplicates_are_untouched(self, monkeypatch):
        rows = [
            _town_row("2026-09-01", "旭丘", "1", "2", "3", "5"),
            _town_row("2026-09-01", "小竹町", "1", "2", "3", "5"),
        ]
        called = []
        monkeypatch.setattr(
            P,
            "_monthly_from_archive",
            lambda *a, **k: called.append(1) or set(),
        )
        kept, resolved, unresolved = P._resolve_duplicates(
            _entry(), rows, [], P.Throttle(interval=0)
        )
        assert len(kept) == 2
        assert (resolved, unresolved) == ([], [])
        assert called == [], "重複が無い月で年度 ZIP を取りに行かないこと"

    def test_picks_the_side_the_monthly_file_corroborates(self, monkeypatch):
        rows = [
            _town_row("2018-12-01", "旭丘", "4867", "3674", "3651", "7325"),
            _town_row("2018-12-01", "旭丘", "4711", "3614", "3598", "7212"),
        ]
        monthly = {(("旭丘",), ("4711", "3614", "3598", "7212"))}
        kept, resolved, unresolved = self._resolve(monkeypatch, rows, monthly)
        assert [r["total"] for r in kept] == ["7212"]
        assert resolved == ["2018-12-01"]
        assert unresolved == []

    def test_collapses_rows_that_are_identical_in_both_sets(self, monkeypatch):
        """人口0の年齢のように2組の値が同じキーは1行に畳む。"""
        rows = [
            _town_row("2018-12-01", "旭丘", "0", "0", "0", "0"),
            _town_row("2018-12-01", "旭丘", "0", "0", "0", "0"),
        ]
        monthly = {(("旭丘",), ("0", "0", "0", "0"))}
        kept, resolved, unresolved = self._resolve(monkeypatch, rows, monthly)
        assert len(kept) == 1
        assert resolved == ["2018-12-01"]

    def test_keeps_both_sides_when_the_monthly_file_is_unavailable(self, monkeypatch):
        rows = [
            _town_row("2018-12-01", "旭丘", "4867", "3674", "3651", "7325"),
            _town_row("2018-12-01", "旭丘", "4711", "3614", "3598", "7212"),
        ]
        kept, resolved, unresolved = self._resolve(monkeypatch, rows, None)
        assert len(kept) == 2, "根拠が無いまま片方を選ばないこと"
        assert unresolved == ["2018-12-01"]
        assert resolved == []

    def test_keeps_both_sides_when_a_key_matches_neither(self, monkeypatch):
        """月次が第3の値を持つキーがあると、そのキーだけ黙って消える。件数で止める。"""
        rows = [
            _town_row("2018-12-01", "旭丘", "4867", "3674", "3651", "7325"),
            _town_row("2018-12-01", "旭丘", "4711", "3614", "3598", "7212"),
            _town_row("2018-12-01", "小竹町", "100", "50", "50", "100"),
            _town_row("2018-12-01", "小竹町", "200", "90", "110", "200"),
        ]
        monthly = {
            (("旭丘",), ("4711", "3614", "3598", "7212")),
            (("小竹町",), ("300", "140", "160", "300")),
        }
        kept, resolved, unresolved = self._resolve(monkeypatch, rows, monthly)
        assert len(kept) == 4, "一部しか突き合わないなら月ごと原典のまま残すこと"
        assert unresolved == ["2018-12-01"]
        assert resolved == []
