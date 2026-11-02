"""Synthetic report history calibrated on real Bogotá open data (spec section 8).

Run from the project root: python -m ml.synthetic
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely import STRtree, points
from shapely.geometry import Point, shape

from ml import config
from ml.features import zone_table

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
GEO_DIR = ROOT / "app" / "static" / "geo"
OUTPUT = DATA_DIR / "synthetic_reports.csv"

WASTE_TYPES = ["household", "construction_debris", "bulky", "organic", "mixed"]
WASTE_WEIGHTS = np.array([0.38, 0.17, 0.15, 0.12, 0.18])
SIZES = ["small", "medium", "large"]


def _features(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def base_level(zones: pd.DataFrame) -> pd.Series:
    """Expected monthly reports per UPZ before seasonality and noise, scaled to the city total."""
    density = zones["population_density"] / zones["population_density"].max()
    scarce_space = 1 / np.log1p(zones["public_space_m2_per_inhabitant"] + 1)
    raw = 0.4 + 1.0 * zones["critical_points"] + 3.0 * density + 2.0 * scarce_space
    return raw / raw.sum() * config.SYNTHETIC_MONTHLY_REPORTS


def monthly_counts(zones: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Poisson counts per UPZ and month with rainy-season peaks and AR(1) persistence."""
    months = pd.date_range(config.SYNTHETIC_START, periods=config.SYNTHETIC_MONTHS, freq="MS")
    base = base_level(zones).to_numpy()
    level = rng.normal(0, config.NOISE_SD, len(zones))
    rows = []
    for month in months:
        level = config.PERSISTENCE * level + rng.normal(0, config.NOISE_SD, len(zones))
        season = config.RAINY_SEASON_FACTOR if month.month in config.RAINY_MONTHS else 1.0
        counts = rng.poisson(base * season * np.exp(level))
        rows += [(code, month, int(n)) for code, n in zip(zones["upz_code"], counts)]
    return pd.DataFrame(rows, columns=["upz_code", "month", "count"])


class PointSampler:
    """Points inside a UPZ, half of them close to the UPZ's real UAESP critical points."""

    def __init__(self, rng: np.random.Generator):
        self.rng = rng
        self.polygons = {f["properties"]["code"]: shape(f["geometry"])
                         for f in _features(GEO_DIR / "upz.geojson")}
        critical = [shape(f["geometry"]) for f in _features(DATA_DIR / "raw" / "pc.geojson")]
        self.critical = {code: [p for p in critical if poly.contains(p)]
                         for code, poly in self.polygons.items()}
        hoods = _features(GEO_DIR / "neighborhoods.geojson")
        self.hood_names = [f["properties"]["name"] for f in hoods]
        self.hood_tree = STRtree([shape(f["geometry"]) for f in hoods])

    def sample(self, code: str) -> Point:
        poly = self.polygons[code]
        near = self.critical[code]
        while True:
            if near and self.rng.random() < config.NEAR_CRITICAL_POINT_SHARE:
                anchor = near[self.rng.integers(len(near))]
                # ~0.0008° is about 90 m in Bogotá.
                p = Point(anchor.x + self.rng.normal(0, 0.0008), anchor.y + self.rng.normal(0, 0.0008))
            else:
                minx, miny, maxx, maxy = poly.bounds
                p = Point(self.rng.uniform(minx, maxx), self.rng.uniform(miny, maxy))
            if poly.contains(p):
                return p

    def neighborhoods(self, pts: list[Point]) -> list[str | None]:
        names: list[str | None] = [None] * len(pts)
        point_idx, hood_idx = self.hood_tree.query(points([(p.x, p.y) for p in pts]), predicate="within")
        for i, h in zip(point_idx, hood_idx):
            if names[i] is None:
                names[i] = self.hood_names[h]
        return names


def _status(age_days: float, rng: np.random.Generator) -> tuple[str, float]:
    """Status today and days from report to its last update. Older reports are mostly closed."""
    if rng.random() < 0.03:
        return "rejected", rng.uniform(0, min(3, age_days))
    p_closed = min(0.9, age_days / 40)
    u = rng.random()
    if u < p_closed:
        return "closed", rng.uniform(1, min(25, max(age_days, 1.5)))
    if u < p_closed + 0.3 * (1 - p_closed):
        return "in_progress", rng.uniform(0, min(5, age_days))
    return "open", 0.0


def generate(seed: int = config.RANDOM_STATE) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    zones = zone_table(
        pd.read_csv(DATA_DIR / "zone_stats.csv", dtype={"upz_code": str, "locality_code": str}),
        pd.read_csv(DATA_DIR / "raw" / "locality_population.csv", dtype={"code": str}),
    )
    counts = monthly_counts(zones, rng)
    sampler = PointSampler(rng)
    zone_by_code = zones.set_index("upz_code")
    debris_bias = (zone_by_code["critical_points"] / zone_by_code["critical_points"].max()).to_dict()
    # Rivers are not in the open data used here, so each UPZ gets a fixed chance of water nearby.
    water_chance = dict(zip(zones["upz_code"], rng.beta(1.2, 6, len(zones))))
    end = pd.Timestamp(config.SYNTHETIC_START) + pd.DateOffset(months=config.SYNTHETIC_MONTHS)

    rows = []
    for code, month, n in counts.itertuples(index=False):
        days = pd.Timestamp(month).days_in_month
        for _ in range(n):
            reported = month + pd.Timedelta(seconds=int(rng.uniform(0, days * 86400)))
            weights = WASTE_WEIGHTS.copy()
            weights[1] *= 1 + 2 * debris_bias[code]
            waste = WASTE_TYPES[rng.choice(5, p=weights / weights.sum())]
            size = SIZES[rng.choice(3, p=[0.35, 0.45, 0.20] if waste != "bulky" else [0.1, 0.4, 0.5])]
            organic = waste in ("organic", "household", "mixed")
            age = (end - reported).total_seconds() / 86400
            status, days_to_update = _status(age, rng)
            p = sampler.sample(code)
            rows.append({
                "upz_code": code,
                "latitude": round(p.y, 6),
                "longitude": round(p.x, 6),
                "reported_at": reported,
                "updated_at": (reported + pd.Timedelta(days=days_to_update)).floor("s"),
                "waste_type": waste,
                "size": size,
                "has_rodents": rng.random() < (0.35 if organic else 0.12),
                "has_insects": rng.random() < (0.40 if organic else 0.10),
                "has_odor": rng.random() < (0.55 if organic else 0.15),
                "near_water": rng.random() < water_chance[code],
                "status": status,
                "_point": p,
            })

    df = pd.DataFrame(rows)
    df["neighborhood"] = sampler.neighborhoods(df.pop("_point").tolist())
    for column in ("reported_at", "updated_at"):
        df[column] = df[column].dt.tz_localize("America/Bogota").dt.tz_convert("UTC")
    return df.sort_values("reported_at").reset_index(drop=True)


if __name__ == "__main__":
    data = generate()
    data.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(data)} reports to {OUTPUT.relative_to(ROOT)}")