"""Reports → one row per UPZ × month with lag features and the next month's risk target."""

import numpy as np
import pandas as pd

from ml import config

REPORT_COLUMNS = ["upz_code", "reported_at", "updated_at", "size", "has_rodents",
                  "has_insects", "has_odor", "near_water", "status"]


class NotEnoughData(Exception):
    """Too few months of reports to build features and validate over time."""


def zone_table(zones: pd.DataFrame, localities: pd.DataFrame) -> pd.DataFrame:
    """Static attributes per UPZ.

    zones: upz_code, locality_code, area_km2, critical_points, public_space_m2_per_inhabitant.
    localities: code, population.
    UPZ population is not published, so each locality's population is split by UPZ area.
    """
    z = zones.copy()
    z["upz_code"] = z["upz_code"].astype(str)
    z["locality_code"] = z["locality_code"].astype(str)
    pop = localities.assign(code=localities["code"].astype(str)).set_index("code")["population"]
    locality_area = z.groupby("locality_code")["area_km2"].transform("sum")
    z["population"] = z["locality_code"].map(pop) * z["area_km2"] / locality_area
    z["population_density"] = z["locality_code"].map(pop) / locality_area
    z["public_space_m2_per_inhabitant"] = z["public_space_m2_per_inhabitant"].fillna(
        z["public_space_m2_per_inhabitant"].median()
    )
    return z[["upz_code", "locality_code", "area_km2", "critical_points",
              "public_space_m2_per_inhabitant", "population", "population_density"]]


def _utc(series: pd.Series) -> pd.Series:
    """Timestamps as naive UTC: months are UTC calendar months, the rule stats_service uses."""
    return pd.to_datetime(series, utc=True).dt.tz_localize(None)


def build_panel(reports: pd.DataFrame, zones: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """One row per UPZ and month, from the first to the last complete month with reports.

    The current UTC month (relative to `now`, default the current time) is still partial, so its
    reports are left out. Every feature of month t uses reports up to the end of month t only.
    `next_rate` is the following month's reports per 10,000 inhabitants (NaN for the last month,
    which is the one we predict from).
    """
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    current_month = now.tz_localize(None).to_period("M").to_timestamp()
    r = reports[reports["status"] != "rejected"].copy()
    r["month"] = _utc(r["reported_at"]).dt.to_period("M").dt.to_timestamp()
    r = r[r["month"] < current_month]
    if r.empty:
        raise NotEnoughData("There are no reports from a complete month yet; "
                            f"training needs {config.MIN_MONTHS} months of them.")
    r["upz_code"] = r["upz_code"].astype(str)
    month_end = r["month"] + pd.offsets.MonthBegin(1)
    updated = _utc(r["updated_at"])
    # Closing is a report's last change, so a closed report closed after month end was still open then.
    r["open_at_end"] = (r["status"] != "closed") | (updated >= month_end)
    r["large"] = r["size"] == "large"
    r["vectors"] = r["has_rodents"] | r["has_insects"] | r["has_odor"]

    monthly = r.groupby(["upz_code", "month"]).agg(
        reports=("size", "size"),
        share_large=("large", "mean"),
        share_vectors=("vectors", "mean"),
        share_near_water=("near_water", "mean"),
        open_at_month_end=("open_at_end", "sum"),
    )

    months = pd.date_range(r["month"].min(), r["month"].max(), freq="MS")
    grid = pd.MultiIndex.from_product([zones["upz_code"], months], names=["upz_code", "month"])
    panel = monthly.reindex(grid).fillna(0).reset_index()
    panel = panel.sort_values(["upz_code", "month"]).reset_index(drop=True)

    by_zone = panel.groupby("upz_code")["reports"]
    for k in (1, 2, 3):
        panel[f"lag_{k}"] = by_zone.shift(k).fillna(0)
    panel["rolling_mean_3"] = by_zone.transform(lambda s: s.rolling(3, min_periods=1).mean())
    panel["change_1"] = panel["reports"] - panel["lag_1"]
    panel["month_of_year"] = panel["month"].dt.month

    panel = panel.merge(zones, on="upz_code", how="left")
    panel["rate"] = panel["reports"] / panel["population"] * config.RATE_PER_INHABITANTS
    next_reports = panel.groupby("upz_code")["reports"].shift(-1)
    panel["next_rate"] = next_reports / panel["population"] * config.RATE_PER_INHABITANTS
    return panel


def tercile_cuts(rates: pd.Series) -> tuple[float, float]:
    low, high = np.quantile(rates, [1 / 3, 2 / 3])
    return float(low), float(high)


def label(rates: pd.Series, cuts: tuple[float, float]) -> pd.Series:
    """low below the first cut, high above the second, medium in between."""
    low, high = cuts
    levels = np.where(rates <= low, "low", np.where(rates <= high, "medium", "high"))
    return pd.Series(levels, index=rates.index)