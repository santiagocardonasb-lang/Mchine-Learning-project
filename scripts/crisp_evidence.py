"""Reproducible CRISP-ML evidence: data quality, before/after, partitions, tuning, overfitting, figures.

Reads only the files in data/ (no database) and writes app/static/crisp/evidence.json plus the
figures shown in the CRISP-ML section of the app. Run: python scripts/crisp_evidence.py
"""
import itertools
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ml import config  # noqa: E402
from ml.features import build_panel, zone_table  # noqa: E402
from ml.train import LEVELS, labelled, make_models, scores, split_months, train  # noqa: E402

OUT = ROOT / "app" / "static" / "crisp"
OUT.mkdir(parents=True, exist_ok=True)
NOW = pd.Timestamp("2026-11-01", tz="UTC")  # the history ends in October 2026
INK, BRAND, SOFT, GREY = "#1f2a26", "#2f6b5a", "#cfe3d9", "#8a948f"
RISK = {"low": "#5f9e7c", "medium": "#d39a4f", "high": "#d9706a"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": GREY, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})

GRIDS = {
    "logistic_regression": [{"C": c} for c in (0.01, 0.1, 1.0, 10.0)],
    "random_forest": [{"n_estimators": n, "max_depth": d, "min_samples_leaf": leaf}
                      for n, d, leaf in itertools.product((100, 300), (4, 8, 12, None), (1, 5, 20))],
}


def build(name, params):
    if name == "logistic_regression":
        return make_pipeline(StandardScaler(), LogisticRegression(
            C=params["C"], max_iter=config.LOGREG_MAX_ITER, class_weight=config.CLASS_WEIGHT))
    return RandomForestClassifier(**params, class_weight=config.CLASS_WEIGHT,
                                  random_state=config.RANDOM_STATE, n_jobs=-1)


def save(fig, name):
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------- data
raw = pd.read_csv(ROOT / "data" / "synthetic_reports.csv", dtype={"upz_code": str})
stats = pd.read_csv(ROOT / "data" / "zone_stats.csv", dtype={"upz_code": str, "locality_code": str})
pop = pd.read_csv(ROOT / "data" / "raw" / "locality_population.csv", dtype={"code": str})
zones = zone_table(stats, pop[["code", "population"]])

# ---------------- data quality (before processing)
reported = pd.to_datetime(raw["reported_at"], utc=True)
updated = pd.to_datetime(raw["updated_at"], utc=True)
allowed = {"waste_type": {"household", "construction_debris", "bulky", "organic", "mixed"},
           "size": {"small", "medium", "large"}, "status": {"open", "in_progress", "closed", "rejected"}}
quality = {
    "reports": {
        "rows": len(raw), "columns": list(raw.columns),
        "missing": {c: int(n) for c, n in raw.isna().sum().items()},
        "exact_duplicates": int(raw.duplicated().sum()),
        "same_place_and_time": int(raw.duplicated(["upz_code", "latitude", "longitude", "reported_at"]).sum()),
        "invalid_categories": {c: int((~raw[c].isin(v)).sum()) for c, v in allowed.items()},
        "updated_before_reported": int((updated < reported).sum()),
        "unknown_upz": int((~raw["upz_code"].isin(stats["upz_code"])).sum()),
        "first": reported.min().strftime("%Y-%m-%d"), "last": reported.max().strftime("%Y-%m-%d"),
        "status_counts": {k: int(v) for k, v in raw["status"].value_counts().items()},
    },
    "zones": {
        "upz": len(stats), "localities": int(stats["locality_code"].nunique()),
        "missing": {c: int(n) for c, n in stats.isna().sum().items() if n},
        "zero_critical_points": int((stats["critical_points"] == 0).sum()),
        "critical_points_total": int(stats["critical_points"].sum()),
        "public_space_imputed_with_median": int(stats["public_space_m2_per_inhabitant"].isna().sum()),
    },
}

# ---------------- processing
panel = build_panel(raw, zones, now=NOW)
rows = panel[panel["next_rate"].notna()].copy()
months = sorted(rows["month"].unique())
train_months, test_months = split_months(months)
rate = rows["rate"]
q1, q3 = rate.quantile([0.25, 0.75])
upper = q3 + 1.5 * (q3 - q1)
quality["panel"] = {
    "rows": len(panel), "labelled_rows": len(rows), "features": config.FEATURES,
    "missing_after": int(rows[config.FEATURES].isna().sum().sum()),
    "rate_iqr_upper_fence": round(float(upper), 3),
    "rate_outliers": int((rate > upper).sum()),
    "rate_outlier_share": round(float((rate > upper).mean()), 4),
    "rate_max": round(float(rate.max()), 3),
}
y_all, cuts = labelled(rows, train_months)

sample_cols = ["upz_code", "reported_at", "waste_type", "size", "has_rodents", "has_odor", "status"]
feature_view = ["upz_code", "month", "reports", "rate", "lag_1", "rolling_mean_3", "share_large",
                "critical_points", "population_density", "next_rate"]
before_after = {
    "raw_sample": raw[raw["upz_code"] == "80"][sample_cols].head(5).astype(str).to_dict("records"),
    "panel_sample": rows[rows["upz_code"] == "80"][feature_view].head(5).assign(
        month=lambda d: d["month"].dt.strftime("%Y-%m"), level=y_all[rows["upz_code"] == "80"].head(5)
    ).round(3).astype(str).to_dict("records"),
}

partitions = {
    "months": [m.strftime("%Y-%m") for m in months],
    "train": [m.strftime("%Y-%m") for m in train_months],
    "test": [m.strftime("%Y-%m") for m in test_months],
    "train_rows": int(rows["month"].isin(train_months).sum()),
    "test_rows": int(rows["month"].isin(test_months).sum()),
    "cuts_from_training_months": [round(c, 3) for c in cuts],
    "folds": [],
}
for train_idx, val_idx in TimeSeriesSplit(n_splits=config.N_SPLITS).split(train_months):
    partitions["folds"].append({"train": f"{train_months[train_idx[0]]:%Y-%m} to {train_months[train_idx[-1]]:%Y-%m}",
                                "validate": f"{train_months[val_idx[0]]:%Y-%m} to {train_months[val_idx[-1]]:%Y-%m}"})

# ---------------- tuning (training months only; the test months are never touched here)
train_rows = rows[rows["month"].isin(train_months)]
experiments = []
for name, grid in GRIDS.items():
    for params in grid:
        fold_val, fold_train = [], []
        for train_idx, val_idx in TimeSeriesSplit(n_splits=config.N_SPLITS).split(train_months):
            tm = [train_months[i] for i in train_idx]
            vm = [train_months[i] for i in val_idx]
            fold = train_rows[train_rows["month"].isin(tm + vm)]
            y, _ = labelled(fold, tm)  # cut points and scaling fitted on the fold's training months only
            is_train = fold["month"].isin(tm)
            model = build(name, params).fit(fold.loc[is_train, config.FEATURES], y[is_train])
            fold_val.append(scores(y[~is_train], model.predict(fold.loc[~is_train, config.FEATURES])))
            fold_train.append(scores(y[is_train], model.predict(fold.loc[is_train, config.FEATURES])))
        experiments.append({
            "model": name, "params": {k: ("None" if v is None else v) for k, v in params.items()},
            "val_macro_f1": float(np.mean([f["macro_f1"] for f in fold_val])),
            "val_macro_f1_std": float(np.std([f["macro_f1"] for f in fold_val])),
            "val_recall_high": float(np.mean([f["recall_high"] for f in fold_val])),
            "train_macro_f1": float(np.mean([f["macro_f1"] for f in fold_train])),
        })
        print(name, params, round(experiments[-1]["val_macro_f1"], 3), flush=True)
for e in experiments:
    e["gap"] = e["train_macro_f1"] - e["val_macro_f1"]
    e["current"] = (e["model"] == "random_forest" and e["params"] == {
        "n_estimators": config.N_ESTIMATORS, "max_depth": config.MAX_DEPTH,
        "min_samples_leaf": config.MIN_SAMPLES_LEAF}) or (e["model"] == "logistic_regression"
                                                           and e["params"] == {"C": config.LOGREG_C})
best = {m: max((e for e in experiments if e["model"] == m), key=lambda e: (e["val_macro_f1"], e["val_recall_high"]))
        for m in GRIDS}

# ---------------- independent test of the configuration in ml/config.py (chosen once, not tuned on test)
test = {}
is_train = rows["month"].isin(train_months)
for name, model in make_models().items():
    model.fit(rows.loc[is_train, config.FEATURES], y_all[is_train])
    test[name] = {**scores(y_all[~is_train], model.predict(rows.loc[~is_train, config.FEATURES])),
                  "train_macro_f1": scores(y_all[is_train], model.predict(rows.loc[is_train, config.FEATURES]))["macro_f1"]}

evidence = {"generated_with": "scripts/crisp_evidence.py", "data_until": "2026-10",
            "quality": quality, "before_after": before_after, "partitions": partitions,
            "experiments": experiments, "best": best, "test": test,
            "class_balance_train": {lvl: int((y_all[is_train] == lvl).sum()) for lvl in LEVELS}}
(OUT / "evidence.json").write_text(json.dumps(evidence, indent=1, default=str))

# ---------------- figures
monthly = raw.assign(month=reported.dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()).groupby("month").size()
fig, ax = plt.subplots(figsize=(8, 3))
ax.bar(monthly.index, monthly.values, width=20, color=[SOFT if m in train_months else RISK["medium"] if m in test_months else GREY for m in monthly.index])
ax.set_ylabel("Reports per month")
ax.set_title("Synthetic history: training months (green), test months (orange)", fontsize=10, color=INK, loc="left")
save(fig, "monthly_reports.png")

fig, ax = plt.subplots(figsize=(8, 2.6))
ax.boxplot(rate, orientation="horizontal", widths=0.5, patch_artist=True, boxprops={"facecolor": SOFT, "color": BRAND},
           medianprops={"color": BRAND}, flierprops={"markeredgecolor": RISK["high"], "markersize": 3})
ax.axvline(upper, color=RISK["high"], ls="--", lw=1)
ax.set_yticks([]); ax.set_xlabel("Reports per 10,000 inhabitants (UPZ-month)")
ax.set_title(f"Rate distribution: {quality['panel']['rate_outliers']} values above the IQR fence (kept, see text)",
             fontsize=10, color=INK, loc="left")
save(fig, "rate_outliers.png")

fig, ax = plt.subplots(figsize=(4.5, 3))
counts = [evidence["class_balance_train"][lvl] for lvl in LEVELS]
ax.bar(LEVELS, counts, color=[RISK[lvl] for lvl in LEVELS])
ax.set_ylabel("Zone-months"); ax.set_title("Target classes in the training months", fontsize=10, color=INK, loc="left")
save(fig, "class_balance.png")

rf = [e for e in experiments if e["model"] == "random_forest" and e["params"]["n_estimators"] == config.N_ESTIMATORS]
depths = ["4", "8", "12", "None"]; leaves = [1, 5, 20]
grid = np.array([[next(e["val_macro_f1"] for e in rf if str(e["params"]["max_depth"]) == d and e["params"]["min_samples_leaf"] == leaf)
                  for leaf in leaves] for d in depths])
fig, ax = plt.subplots(figsize=(4.8, 3.6))
im = ax.imshow(grid, cmap="Greens", vmin=grid.min() - 0.01, vmax=grid.max())
ax.set_xticks(range(3), leaves); ax.set_yticks(range(4), depths)
ax.set_xlabel("min_samples_leaf"); ax.set_ylabel("max_depth")
for i in range(4):
    for j in range(3):
        ax.text(j, i, f"{grid[i, j]:.3f}", ha="center", va="center", fontsize=9,
                color="white" if grid[i, j] > grid.mean() else INK)
ax.set_title(f"Random forest, {config.N_ESTIMATORS} trees: CV macro-F1", fontsize=10, color=INK, loc="left")
save(fig, "tuning_heatmap.png")

fig, ax = plt.subplots(figsize=(7.5, 3.4))
order = sorted(rf, key=lambda e: (depths.index(str(e["params"]["max_depth"])), e["params"]["min_samples_leaf"]))
labels = [f"d={e['params']['max_depth']}\nl={e['params']['min_samples_leaf']}" for e in order]
x = np.arange(len(order))
ax.plot(x, [e["train_macro_f1"] for e in order], "o-", color=RISK["high"], label="Training folds")
ax.plot(x, [e["val_macro_f1"] for e in order], "o-", color=BRAND, label="Validation folds")
ax.set_xticks(x, labels, fontsize=7.5); ax.set_ylabel("Macro-F1"); ax.legend(frameon=False, fontsize=8)
ax.set_title("Overfitting check: deeper trees fit training months better but do not validate better",
             fontsize=10, color=INK, loc="left")
save(fig, "overfitting.png")

names = ["baseline", "logistic_regression", "random_forest"]
fig, ax = plt.subplots(figsize=(6, 3.2))
cv_vals = [best[n]["val_macro_f1"] if n in best else None for n in names]
base_cv = []
for train_idx, val_idx in TimeSeriesSplit(n_splits=config.N_SPLITS).split(train_months):
    tm = [train_months[i] for i in train_idx]; vm = [train_months[i] for i in val_idx]
    fold = train_rows[train_rows["month"].isin(tm + vm)]; y, _ = labelled(fold, tm); it = fold["month"].isin(tm)
    base_cv.append(scores(y[~it], make_models()["baseline"].fit(fold.loc[it, config.FEATURES], y[it]).predict(fold.loc[~it, config.FEATURES]))["macro_f1"])
current = {n: next(e for e in experiments if e["model"] == n and e["current"]) for n in GRIDS}
means = [np.mean(base_cv), current["logistic_regression"]["val_macro_f1"], current["random_forest"]["val_macro_f1"]]
stds = [np.std(base_cv), current["logistic_regression"]["val_macro_f1_std"], current["random_forest"]["val_macro_f1_std"]]
tests = [test[n]["macro_f1"] for n in names]
x = np.arange(3)
ax.bar(x - 0.18, means, 0.36, yerr=stds, capsize=3, color=SOFT, edgecolor=BRAND, label="CV mean ± std")
ax.bar(x + 0.18, tests, 0.36, color=BRAND, label="Test (independent)")
ax.set_xticks(x, ["Baseline", "Logistic regression", "Random forest"]); ax.set_ylabel("Macro-F1")
ax.legend(frameon=False, fontsize=8); ax.set_title("Model comparison", fontsize=10, color=INK, loc="left")
save(fig, "model_comparison.png")
evidence["baseline_cv"] = {"mean": float(np.mean(base_cv)), "std": float(np.std(base_cv))}
final = train(panel)  # exactly what `flask train` stores for the served model
evidence["final_run"] = {"chosen_model": final.model_name, "metrics": final.metrics, "n_rows": final.n_rows}
cm = np.array(final.metrics["test"]["confusion_matrix"])
fig, ax = plt.subplots(figsize=(3.8, 3.4))
ax.imshow(cm, cmap="Greens")
ax.set_xticks(range(3), LEVELS); ax.set_yticks(range(3), LEVELS)
ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
for i in range(3):
    for j in range(3):
        ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else INK)
ax.set_title("Test confusion matrix", fontsize=10, color=INK, loc="left")
save(fig, "confusion_matrix.png")
imp = list(final.metrics["feature_importance"].items())[:10][::-1]
fig, ax = plt.subplots(figsize=(6, 3.4))
ax.barh([k for k, _ in imp], [v for _, v in imp], color=BRAND)
ax.set_xlabel("Importance"); ax.set_title("Top 10 features of the served model", fontsize=10, color=INK, loc="left")
save(fig, "feature_importance.png")

# ---------------- initial monitoring test with SIMULATED operational months
from collections import Counter  # noqa: E402

from app.services.monitoring_service import psi, share_shifts  # noqa: E402  same functions as /admin/monitoring

rng = np.random.default_rng(7)
reference = rows.loc[rows["month"].isin(train_months), "rate"]
last = rows[rows["month"] == months[-1]]
ref_types = Counter(raw.loc[reported.dt.tz_localize(None) < train_months[-1] + pd.offsets.MonthBegin(1), "waste_type"])
floor = config.PERFORMANCE_DROP_FRACTION * final.metrics["cv"][final.model_name]["macro_f1"]["mean"]
scenarios = []
for name, factor, debris_extra, live_f1 in (("Stable month", 1.0, 0.0, 0.58), ("Report surge", 1.8, 0.20, 0.44)):
    rates = last["rate"].to_numpy() * factor * rng.lognormal(0, 0.15, len(last))
    types = Counter({k: v * (1 - debris_extra) for k, v in ref_types.items()})
    types["construction_debris"] += debris_extra * sum(ref_types.values())
    shift = max(abs(r["change"]) for r in share_shifts(ref_types, types))
    value = psi(reference, rates)
    scenarios.append({"label": "SIMULATED", "scenario": name, "psi": round(value, 3),
                      "psi_flag": bool(value > config.DRIFT_PSI_THRESHOLD), "max_share_shift": round(shift, 3),
                      "share_flag": bool(shift > config.DRIFT_SHARE_THRESHOLD), "live_macro_f1": live_f1,
                      "performance_floor": round(floor, 3), "performance_flag": live_f1 < floor,
                      "action": "retrain" if (value > config.DRIFT_PSI_THRESHOLD or shift > config.DRIFT_SHARE_THRESHOLD
                                              or live_f1 < floor) else "none"})
evidence["simulated_monitoring"] = scenarios
with open(OUT / "simulated_monitoring.log", "w") as log:
    for s in scenarios:
        log.write(json.dumps({"event": "monitoring_check", **s}) + chr(10))
(OUT / "evidence.json").write_text(json.dumps(evidence, indent=1, default=str))

(OUT / "evidence.json").write_text(json.dumps(evidence, indent=1, default=str))
print("simulated:", scenarios)
print("best:", {m: (b["params"], round(b["val_macro_f1"], 4)) for m, b in best.items()})
print("current:", {m: (c["params"], round(c["val_macro_f1"], 4), round(c["val_macro_f1_std"], 4)) for m, c in current.items()})
print("test:", {n: round(t["macro_f1"], 4) for n, t in test.items()})
print("quality:", json.dumps(quality["reports"]["missing"]), quality["reports"]["exact_duplicates"], quality["panel"])
