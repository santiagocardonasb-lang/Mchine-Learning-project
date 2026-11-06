
import pandas as pd
import pytest

from ml.features import NotEnoughData, build_panel, label, tercile_cuts, zone_table

ZONES = zone_table(
    pd.DataFrame({"upz_code": ["1", "2"], "locality_code": ["1", "1"], "area_km2": [1.0, 3.0],
                  "critical_points": [4, 0], "public_space_m2_per_inhabitant": [2.0, None]}),
    pd.DataFrame({"code": ["1"], "population": [40_000]}),
)


def report(upz, when, status="open", updated=None, size="small", rodents=False):
    return {"upz_code": upz, "reported_at": pd.Timestamp(when, tz="UTC"),
            "updated_at": pd.Timestamp(updated or when, tz="UTC"), "size": size,
            "has_rodents": rodents, "has_insects": False, "has_odor": False,
            "near_water": False, "status": status}


def panel_of(*reports, now=None):
    return build_panel(pd.DataFrame(list(reports)), ZONES, now=now)


def row(panel, upz, month):
    return panel[(panel["upz_code"] == upz) & (panel["month"] == pd.Timestamp(month))].iloc[0]


def test_zone_population_is_split_by_area():
    assert ZONES.set_index("upz_code")["population"].to_dict() == {"1": 10_000, "2": 30_000}
    assert ZONES["public_space_m2_per_inhabitant"].notna().all()


def test_panel_has_every_zone_and_month_with_zero_fill():
    panel = panel_of(report("1", "2026-01-10"), report("1", "2026-03-05"))

    assert len(panel) == 2 * 3
    assert row(panel, "2", "2026-02-01")["reports"] == 0


def test_features_use_only_past_months_and_target_is_next_month():
    panel = panel_of(
        report("1", "2026-01-10"),
        report("1", "2026-02-10"), report("1", "2026-02-11"),
        report("1", "2026-03-10"), report("1", "2026-03-11"), report("1", "2026-03-12"),
    )
    feb = row(panel, "1", "2026-02-01")

    assert feb["reports"] == 2
    assert feb["lag_1"] == 1
    assert feb["change_1"] == 1
    # March has 3 reports for 10,000 inhabitants: the target belongs to the next month only.
    assert feb["next_rate"] == pytest.approx(3.0)
    assert pd.isna(row(panel, "1", "2026-03-01")["next_rate"])


def test_rejected_reports_are_left_out():
    panel = panel_of(report("1", "2026-01-10"), report("1", "2026-01-11", status="rejected"))

    assert row(panel, "1", "2026-01-01")["reports"] == 1


def test_report_closed_after_month_end_counts_as_open_then():
    panel = panel_of(
        report("1", "2026-01-10", status="closed", updated="2026-02-03"),
        report("1", "2026-01-12", status="closed", updated="2026-01-20"),
    )

    assert row(panel, "1", "2026-01-01")["open_at_month_end"] == 1


def test_months_are_utc_calendar_months():
    panel = panel_of(
        report("1", "2026-01-31 23:30"),
        # 11:30 pm on January 31 in Bogotá is already February 1 in UTC.
        {**report("1", "2026-02-10"), "reported_at": pd.Timestamp("2026-01-31 23:30", tz="America/Bogota")},
    )

    assert row(panel, "1", "2026-01-01")["reports"] == 1
    assert row(panel, "1", "2026-02-01")["reports"] == 1


def test_current_utc_month_is_left_out():
    reports = [report("1", "2026-01-10"), report("1", "2026-02-10"), report("1", "2026-03-02")]
    panel = panel_of(*reports, now=pd.Timestamp("2026-03-15", tz="UTC"))

    assert sorted(panel["month"].unique()) == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")]
    assert pd.isna(row(panel, "1", "2026-02-01")["next_rate"])


def test_only_partial_month_reports_are_not_enough():
    with pytest.raises(NotEnoughData):
        panel_of(report("1", "2026-03-02"), now=pd.Timestamp("2026-03-15", tz="UTC"))


def test_tercile_labels():
    rates = pd.Series([0, 1, 2, 3, 4, 5])
    cuts = tercile_cuts(rates)

    assert list(label(rates, cuts)) == ["low", "low", "medium", "medium", "high", "high"]
