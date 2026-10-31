import csv
import json
from pathlib import Path

from app.extensions import db
from app.models import Locality, Upz

ROOT = Path(__file__).resolve().parent.parent
GEO_DIR = ROOT / "app" / "static" / "geo"
ZONE_STATS = ROOT / "data" / "zone_stats.csv"
POPULATION = ROOT / "data" / "raw" / "locality_population.csv"


def load_features(name):
    return json.loads((GEO_DIR / name).read_text(encoding="utf-8"))["features"]


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_localities_exclude_rural_sumapaz():
    features = load_features("localities.geojson")
    codes = {f["properties"]["code"] for f in features}

    assert len(features) == 19
    assert "20" not in codes
    assert all(set(f["properties"]) == {"code", "name"} for f in features)


def test_every_upz_has_a_known_locality():
    features = load_features("upz.geojson")
    locality_codes = {f["properties"]["code"] for f in load_features("localities.geojson")}

    assert len(features) == 112
    for feature in features:
        assert feature["properties"]["locality_code"] in locality_codes


def test_critical_points_sum_to_uaesp_total():
    rows = read_csv(ZONE_STATS)

    assert len(rows) == 112
    assert sum(int(r["critical_points"]) for r in rows) == 478


def test_collection_days_are_between_zero_and_seven():
    rows = read_csv(ZONE_STATS)

    for row in rows:
        days = float(row["collection_days_per_week"])
        assert 0 <= days <= 7
        if row["critical_points"] == "0":
            assert days == 0


def test_locality_population_covers_the_19_urban_localities():
    rows = read_csv(POPULATION)

    assert len(rows) == 19
    assert list(rows[0]) == ["code", "name", "population", "year", "source_url"]
    assert all(int(r["population"]) > 0 for r in rows)


def test_geojson_files_are_small_enough_for_the_browser():
    for name in ("localities.geojson", "upz.geojson"):
        assert (GEO_DIR / name).stat().st_size < 1.5 * 1024 * 1024
    assert (GEO_DIR / "neighborhoods.geojson").stat().st_size <= 3 * 1024 * 1024


def test_neighborhoods_only_carry_code_and_name():
    features = load_features("neighborhoods.geojson")

    assert len(features) > 500
    assert all(set(f["properties"]) == {"code", "name"} for f in features)


def test_load_zones_is_idempotent(app, db_session):
    runner = app.test_cli_runner()

    for _ in range(2):
        result = runner.invoke(args=["load-zones"])
        assert result.exit_code == 0, result.output

    assert db.session.query(Locality).count() == 19
    assert db.session.query(Upz).count() == 112
    assert db.session.query(db.func.sum(Upz.critical_points)).scalar() == 478
