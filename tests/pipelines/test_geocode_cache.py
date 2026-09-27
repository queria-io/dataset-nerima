"""ジオコーディング結果のキャッシュ。

ABR の配布は日本国外からは取れず、GitHub ホストランナーからは zip でないファイルが返る。
毎回引きに行くと週次の更新が必ず落ちるので、結果をコミットして持つ。ここで押さえるのは
「キャッシュが揃っていれば ABR に触らない」ことと「引けないときに座標を落とさず止まる」ことの2つ。
"""

import json

import pytest

from pipelines import geocode as G


@pytest.fixture
def repo(tmp_path):
    """bosai の NDJSON を1本だけ持つ作業ディレクトリ。"""
    bosai = tmp_path / "bosai"
    bosai.mkdir()
    rows = [
        {"name": "A", "address": "旭丘2-21-1"},
        {"name": "B", "address": "東京都練馬区豊玉北6-12-1"},
    ]
    (bosai / "disaster_well.ndjson").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    for other in ("evacuation_base", "homecoming_support_station", "emergency_water_station"):
        (bosai / f"{other}.ndjson").write_text("", encoding="utf-8")
    return tmp_path


def _cached(address, lat=35.7, lon=139.6, level="residential_block"):
    return {"address": address, "geo_lat": lat, "geo_lon": lon, "geo_level": level}


class TestGeocodeInput:
    @pytest.mark.parametrize(
        ("address", "expected"),
        [
            ("旭丘2-21-1", "東京都練馬区旭丘2-21-1"),
            ("練馬区豊玉北6-12-1", "東京都練馬区豊玉北6-12-1"),
            ("東京都練馬区豊玉北6-12-1", "東京都練馬区豊玉北6-12-1"),
            # 区外に施設を持っていても、存在しない住所を組み立てない
            ("山梨県北杜市1-1", "山梨県北杜市1-1"),
        ],
    )
    def test_prefixes_only_when_needed(self, address, expected):
        assert G.geocode_input(address) == expected


class TestCacheFile:
    def test_round_trip_is_sorted(self, tmp_path):
        path = tmp_path / "cache.ndjson"
        G.save_cache(path, {"B": _cached("B"), "A": _cached("A")})
        assert [json.loads(l)["address"] for l in path.read_text(encoding="utf-8").splitlines()] == ["A", "B"]
        assert set(G.load_cache(path)) == {"A", "B"}

    def test_missing_file_is_an_empty_cache(self, tmp_path):
        assert G.load_cache(tmp_path / "none.ndjson") == {}


class TestRecord:
    def test_keeps_usable_coordinates(self):
        record = G._record("x", {"coordinate_level": "residential_detail", "lat": 35.7, "lon": 139.6})
        assert (record["geo_lat"], record["geo_level"]) == (35.7, "residential_detail")

    @pytest.mark.parametrize("level", ["city", "prefecture", "unknown"])
    def test_drops_coarse_levels(self, level):
        """市区町村の代表点を採ると、地図に区役所へピンが集まるだけになる。"""
        record = G._record("x", {"coordinate_level": level, "lat": 35.7, "lon": 139.6})
        assert record["geo_lat"] is None
        assert record["geo_level"] is None

    def test_no_result_at_all(self):
        assert G._record("x", None)["geo_lat"] is None


class TestGeocode:
    def test_full_cache_does_not_touch_abr(self, repo, monkeypatch):
        cache = repo / "cache.ndjson"
        G.save_cache(cache, {
            "旭丘2-21-1": _cached("旭丘2-21-1"),
            "東京都練馬区豊玉北6-12-1": _cached("東京都練馬区豊玉北6-12-1"),
        })
        monkeypatch.setattr(
            G, "_resolve", lambda *a, **k: pytest.fail("キャッシュが揃っているのに ABR を引いた")
        )
        G.geocode(str(repo / "bosai"), str(repo / "out"), str(cache))
        written = [
            json.loads(l)
            for l in (repo / "out" / "addresses.ndjson").read_text(encoding="utf-8").splitlines()
        ]
        assert {r["address"] for r in written} == {"旭丘2-21-1", "東京都練馬区豊玉北6-12-1"}

    def test_output_holds_only_the_addresses_in_use(self, repo, monkeypatch):
        """過去に引いた住所はキャッシュに残すが、出力には現行のぶんだけ入れる。"""
        cache = repo / "cache.ndjson"
        G.save_cache(cache, {
            "旭丘2-21-1": _cached("旭丘2-21-1"),
            "東京都練馬区豊玉北6-12-1": _cached("東京都練馬区豊玉北6-12-1"),
            "もう使っていない住所": _cached("もう使っていない住所"),
        })
        monkeypatch.setattr(G, "_resolve", lambda *a, **k: pytest.fail("引いてはいけない"))
        G.geocode(str(repo / "bosai"), str(repo / "out"), str(cache))
        written = (repo / "out" / "addresses.ndjson").read_text(encoding="utf-8")
        assert "もう使っていない住所" not in written
        # キャッシュ側は消さない
        assert "もう使っていない住所" in G.load_cache(cache)

    def test_new_address_without_node_stops_the_build(self, repo, monkeypatch):
        cache = repo / "cache.ndjson"
        G.save_cache(cache, {"旭丘2-21-1": _cached("旭丘2-21-1")})
        monkeypatch.setattr(G, "_node_major", lambda: None)
        with pytest.raises(SystemExit) as raised:
            G.geocode(str(repo / "bosai"), str(repo / "out"), str(cache))
        message = str(raised.value)
        assert "キャッシュに無い住所が 1 件" in message
        assert "東京都練馬区豊玉北6-12-1" in message
        assert G.CACHE_PATH in message, "直し方にキャッシュの場所を書くこと"

    def test_new_address_on_node_24_stops_the_build(self, repo, monkeypatch):
        cache = repo / "cache.ndjson"
        G.save_cache(cache, {"旭丘2-21-1": _cached("旭丘2-21-1")})
        monkeypatch.setattr(G, "_node_major", lambda: 24)
        with pytest.raises(SystemExit) as raised:
            G.geocode(str(repo / "bosai"), str(repo / "out"), str(cache))
        assert "better-sqlite3" in str(raised.value)

    def test_new_address_merges_into_the_cache(self, repo, monkeypatch):
        cache = repo / "cache.ndjson"
        G.save_cache(cache, {"旭丘2-21-1": _cached("旭丘2-21-1")})
        monkeypatch.setattr(
            G,
            "_resolve",
            lambda missing, dest, **k: {a: _cached(a, 35.8, 139.7) for a in missing},
        )
        G.geocode(str(repo / "bosai"), str(repo / "out"), str(cache))
        saved = G.load_cache(cache)
        assert set(saved) == {"旭丘2-21-1", "東京都練馬区豊玉北6-12-1"}
        assert saved["東京都練馬区豊玉北6-12-1"]["geo_lat"] == 35.8

    def test_no_addresses_at_all_is_an_error(self, tmp_path):
        empty = tmp_path / "bosai"
        empty.mkdir()
        with pytest.raises(SystemExit):
            G.geocode(str(empty), str(tmp_path / "out"), str(tmp_path / "cache.ndjson"))
