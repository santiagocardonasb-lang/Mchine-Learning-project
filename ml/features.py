"""Build the UPZ-month panel and next-month risk target."""

import numpy as np
import pandas as pd

from ml import config


def zone_table(upzs: pd.DataFrame, localities: pd.DataFrame) -> pd.DataFrame:
    """Combine UPZ and locality information, allocating population by area."""
    zones = upzs.copy()
    localities = localities.copy()

    zones["upz_code"] = zones["upz_code"].astype(str)
    zones["locality_code"] = zones["locality_code"].astype(str)
    localities["code"] = localities["code"].astype(str)

    zones = zones.merge(
        localities[["code", "population"]],
        left_on="locality_code",
        right_on="code",
        how="left",
    )

    total_area = zones.groupby("locality_code")["area_km2"].transform("sum")
    zones["population"] = (
        zones["population"] * zones["area_km2"] / total_area
    ).round().astype(int)

    zones["public_space_m2_per_inhabitant"] = (
        zones["public_space_m2_per_inhabitant"].fillna(
            zones["public_space_m2_per_inhabitant"].median()
        )
    )

    return zones.drop(columns=["code"])


def build_panel(reports: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    """Build one row per UPZ and month, using only information available then."""
    data = reports.copy()

    if data.empty:
        return pd.DataFrame()

    data["upz_code"] = data["upz_code"].astype(str)
    data["reported_at"] = pd.to_datetime(data["reported_at"], utc=True).dt.tz_convert(
        config.TIMEZONE
    )
    data["updated_at"] = pd.to_datetime(data["updated_at"], utc=True).dt.tz_convert(
        config.TIMEZONE
    )

    data = data[data["status"] != "rejected"].copy()

    data["month"] = data["reported_at"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()

    start = data["month"].min()
    end = data["month"].max()
    months = pd.date_range(start, end, freq="MS")

    upz_codes = zones["upz_code"].astype(str).unique()

    panel = pd.MultiIndex.from_product(
        [upz_codes, months], names=["upz_code", "month"]
    ).to_frame(index=False)

    data["large"] = data["size"].eq("large").astype(int)
    data["vectors"] = (
        data["has_rodents"] | data["has_insects"]
    ).astype(int)
    data["near_water_flag"] = data["near_water"].astype(int)

    monthly = data.groupby(["upz_code", "month"]).agg(
        reports=("upz_code", "size"),
        large=("large", "sum"),
        vectors=("vectors", "sum"),
        near_water=("near_water_flag", "sum"),
    ).reset_index()

    panel = panel.merge(monthly, on=["upz_code", "month"], how="left")

    count_columns = ["reports", "large", "vectors", "near_water"]
    panel[count_columns] = panel[count_columns].fillna(0)

    panel = panel.merge(zones, on="upz_code", how="left")

    panel["rate"] = (
        panel["reports"] / panel["population"] * config.RATE_PER_INHABITANTS
    )

    for column in ["large", "vectors", "near_water"]:
        panel[f"share_{column}"] = np.where(
            panel["reports"] > 0,
            panel[column] / panel["reports"],
            0,
        )

    panel["month_of_year"] = panel["month"].dt.month

    panel = panel.sort_values(["upz_code", "month"]).reset_index(drop=True)

    grouped = panel.groupby("upz_code", group_keys=False)

    panel["lag_1"] = grouped["reports"].shift(1)
    panel["lag_2"] = grouped["reports"].shift(2)
    panel["lag_3"] = grouped["reports"].shift(3)

    panel["rolling_mean_3"] = grouped["reports"].transform(
        lambda values: values.shift(1).rolling(3, min_periods=1).mean()
    )

    panel["change_1"] = panel["reports"] - panel["lag_1"]

    panel[["lag_1", "lag_2", "lag_3"]] = panel[
        ["lag_1", "lag_2", "lag_3"]
    ].fillna(0)

    panel["rolling_mean_3"] = panel["rolling_mean_3"].fillna(0)
    panel["change_1"] = panel["change_1"].fillna(0)

    report_months = data.groupby(["upz_code", "month"]).size().rename("count")
    report_months = report_months.reset_index()

    closed = data.assign(
        closed_on_time=(
            (data["status"] == "closed")
            & (data["updated_at"].dt.tz_localize(None) < (
                data["month"] + pd.offsets.MonthBegin(1)
            ))
        ).astype(int)
    )

    closed_monthly = closed.groupby(["upz_code", "month"])[
        "closed_on_time"
    ].sum().reset_index()

    panel = panel.merge(
        closed_monthly, on=["upz_code", "month"], how="left"
    )

    panel["open_at_month_end"] = (
        panel["reports"] - panel["closed_on_time"].fillna(0)
    ).clip(lower=0)

    panel["critical_points"] = panel["critical_points"].fillna(0)

    panel["next_rate"] = grouped["rate"].shift(-1)

    return panel.drop(
        columns=["large", "vectors", "near_water", "closed_on_time"],
        errors="ignore",
    )


def tercile_cuts(rates: pd.Series) -> tuple[float, float]:
    """Calculate the lower and upper tercile thresholds."""
    clean = rates.dropna()

    return (
        float(clean.quantile(1 / 3)),
        float(clean.quantile(2 / 3)),
    )


def label(rates: pd.Series, cuts: tuple[float, float]) -> pd.Series:
    """Assign low, medium, or high risk using the supplied thresholds."""
    lower, upper = cuts

    return pd.Series(
        np.select(
            [rates <= lower, rates <= upper],
            ["low", "medium"],
            default="high",
        ),
        index=rates.index,
    )