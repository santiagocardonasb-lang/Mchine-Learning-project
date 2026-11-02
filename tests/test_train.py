import numpy as np
import pandas as pd
import pytest

from ml import config
from ml.features import NotEnoughData, build_panel, zone_table
from ml.train import cross_validate, split_months, train


def report(upz, when):
    return {"upz_code": upz, "reported_at": pd.Timestamp(when, tz="America/Bogota"),
            "updated_at": pd.Timestamp(when, tz="America/Bogota"), "size": "small",
            "has_rodents": False, "has_insects": False, "has_odor": False,
            "near_water": False, "status": "open"}


def synthetic_panel(n_months=18):
    zones = zone_table(
        pd.DataFrame({"upz_code": [str(i) for i in range(30)], "locality_code": ["1"] * 30,
                      "area_km2": [1.0] * 30, "critical_points": list(range(30)),
                      "public_space_m2_per_inhabitant": [5.0] * 30}),
        pd.DataFrame({"code": ["1"], "population": [300_000]}),
    )
    rng = np.random.default_rng(1)
    rows = []
    months = pd.date_range("2025-01-01", periods=n_months, freq="MS")
    for code, cp in zip(zones["upz_code"], range(30)):
        for month in months:
            for _ in range(rng.poisson(1 + cp / 3)):
                rows.append(report(code, month + pd.Timedelta(days=int(rng.integers(0, 27)))))
    return build_panel(pd.DataFrame(rows), zones)


def test_split_keeps_test_months_last():
    months = list(range(20))
    train_months, test_months = split_months(months)

    assert test_months == [16, 17, 18, 19]
    assert max(train_months) < min(test_months)


def test_cross_validation_reports_mean_and_std_per_model():
    panel = synthetic_panel()
    rows = panel[panel["next_rate"].notna()]
    months = sorted(rows["month"].unique())
    cv = cross_validate(rows, months)

    assert set(cv) == {"baseline", "logistic_regression", "random_forest"}
    for metrics in cv.values():
        assert set(metrics) == {"macro_f1", "recall_high", "accuracy"}
        assert {"mean", "std"} == set(metrics["macro_f1"])


def test_train_reports_all_models_and_predicts_next_month(monkeypatch):
    monkeypatch.setattr(config, "N_ESTIMATORS", 20)
    result = train(synthetic_panel())
    m = result.metrics

    assert m["chosen_model"] in ("logistic_regression", "random_forest")
    assert m["cv"]["random_forest"]["macro_f1"]["mean"] > m["cv"]["baseline"]["macro_f1"]["mean"]
    assert len(m["test"]["confusion_matrix"]) == 3
    assert m["period"] == "2026-07-01"  # last month is 2026-06
    assert len(result.predictions) == 30
    assert set(result.predictions["level"]) <= {"low", "medium", "high"}
    assert result.params["N_SPLITS"] == config.N_SPLITS


def test_train_needs_enough_months():
    with pytest.raises(NotEnoughData):
        train(synthetic_panel(n_months=6))