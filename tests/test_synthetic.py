import numpy as np
import pandas as pd

from ml import config
from ml.features import zone_table
from ml.synthetic import base_level, monthly_counts

ZONES = zone_table(
    pd.DataFrame({"upz_code": ["1", "2"], "locality_code": ["1", "1"], "area_km2": [1.0, 3.0],
                  "critical_points": [4, 0], "public_space_m2_per_inhabitant": [2.0, None]}),
    pd.DataFrame({"code": ["1"], "population": [40_000]}),
)


def test_synthetic_counts_peak_in_rainy_months():
    counts = monthly_counts(ZONES, np.random.default_rng(0))
    by_month = counts.groupby(counts["month"].dt.month)["count"].mean()

    assert by_month[list(config.RAINY_MONTHS)].mean() > by_month.drop(list(config.RAINY_MONTHS)).mean()


def test_zone_without_critical_points_still_gets_reports():
    base = base_level(ZONES)

    assert (base > 0).all()
    assert base.iloc[0] > base.iloc[1]  # UPZ 1 has 4 critical points, UPZ 2 none