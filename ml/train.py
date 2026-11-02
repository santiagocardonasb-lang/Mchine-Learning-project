"""Baseline and two models, temporal validation, metrics and next-month predictions."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support, recall_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml import config
from ml.features import NotEnoughData, label, tercile_cuts

LEVELS = list(config.RISK_LEVELS)
MODEL_NAMES = {"baseline": "Baseline (most frequent)",
               "logistic_regression": "Logistic regression",
               "random_forest": "Random forest"}


@dataclass
class TrainResult:
    model: object
    model_name: str
    params: dict
    metrics: dict
    predictions: pd.DataFrame  # upz_code, period, level, probability
    n_rows: int


def make_models() -> dict:
    return {
        "baseline": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(C=config.LOGREG_C, max_iter=config.LOGREG_MAX_ITER,
                               class_weight=config.CLASS_WEIGHT),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=config.N_ESTIMATORS, max_depth=config.MAX_DEPTH,
            min_samples_leaf=config.MIN_SAMPLES_LEAF, class_weight=config.CLASS_WEIGHT,
            random_state=config.RANDOM_STATE, n_jobs=-1,
        ),
    }


def scores(y_true, y_pred) -> dict:
    return {
        "macro_f1": float(f1_score(y_true, y_pred, labels=LEVELS, average="macro", zero_division=0)),
        "recall_high": float(recall_score(y_true, y_pred, labels=["high"], average="macro", zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
    }


def split_months(months: list) -> tuple[list, list]:
    n_test = max(1, round(len(months) * config.TEST_MONTHS_FRACTION))
    return months[:-n_test], months[-n_test:]


def labelled(rows: pd.DataFrame, cut_months: list) -> tuple[pd.Series, tuple[float, float]]:
    """Levels for `rows`, with tercile cuts computed on the rows of `cut_months` only."""
    cuts = tercile_cuts(rows.loc[rows["month"].isin(cut_months), "next_rate"])
    return label(rows["next_rate"], cuts), cuts


def cross_validate(rows: pd.DataFrame, months: list) -> dict:
    """TimeSeriesSplit over whole months: every fold trains on earlier months than it tests on."""
    folds = {name: [] for name in MODEL_NAMES}
    for train_idx, test_idx in TimeSeriesSplit(n_splits=config.N_SPLITS).split(months):
        train_months = [months[i] for i in train_idx]
        test_months = [months[i] for i in test_idx]
        fold = rows[rows["month"].isin(train_months + test_months)]
        y, _ = labelled(fold, train_months)
        is_train = fold["month"].isin(train_months)
        for name, model in make_models().items():
            model.fit(fold.loc[is_train, config.FEATURES], y[is_train])
            folds[name].append(scores(y[~is_train], model.predict(fold.loc[~is_train, config.FEATURES])))
    return {
        name: {metric: {"mean": float(np.mean([f[metric] for f in results])),
                        "std": float(np.std([f[metric] for f in results]))}
               for metric in ("macro_f1", "recall_high", "accuracy")}
        for name, results in folds.items()
    }


def holdout(rows: pd.DataFrame, train_months: list, test_months: list, model_name: str) -> dict:
    y, cuts = labelled(rows, train_months)
    is_train = rows["month"].isin(train_months)
    model = make_models()[model_name].fit(rows.loc[is_train, config.FEATURES], y[is_train])
    y_test, y_pred = y[~is_train], model.predict(rows.loc[~is_train, config.FEATURES])
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, labels=LEVELS, zero_division=0
    )
    return {
        **scores(y_test, y_pred),
        "per_class": {level: {"precision": float(p), "recall": float(r), "f1": float(f), "support": int(s)}
                      for level, p, r, f, s in zip(LEVELS, precision, recall, f1, support)},
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=LEVELS).tolist(),
        "cuts": list(cuts),
        "test_months": [m.strftime("%Y-%m") for m in test_months],
    }


def feature_importance(model, model_name: str) -> dict:
    if model_name == "random_forest":
        values = model.feature_importances_
    elif model_name == "logistic_regression":
        values = np.abs(model[-1].coef_).mean(axis=0)
        values = values / values.sum()
    else:
        return {}
    ranked = sorted(zip(config.FEATURES, values), key=lambda item: -item[1])
    return {name: float(value) for name, value in ranked}


def train(panel: pd.DataFrame) -> TrainResult:
    rows = panel[panel["next_rate"].notna()]
    months = sorted(rows["month"].unique())
    if len(months) < config.MIN_MONTHS:
        raise NotEnoughData(f"Training needs {config.MIN_MONTHS} months of reports, found {len(months)}.")
    train_months, test_months = split_months(months)

    cv = cross_validate(rows[rows["month"].isin(train_months)], train_months)
    candidates = [name for name in MODEL_NAMES if name != "baseline"]
    chosen = max(candidates, key=lambda n: (cv[n]["macro_f1"]["mean"], cv[n]["recall_high"]["mean"]))
    test = holdout(rows, train_months, test_months, chosen)
    baseline_test = holdout(rows, train_months, test_months, "baseline")

    # The served model learns from every labelled month, with cuts from all of them.
    y, cuts = labelled(rows, months)
    model = make_models()[chosen].fit(rows[config.FEATURES], y)

    latest = panel[panel["month"] == panel["month"].max()]
    probabilities = model.predict_proba(latest[config.FEATURES])
    classes = list(model.classes_)
    period = (latest["month"].iloc[0] + pd.offsets.MonthBegin(1)).date()
    predictions = pd.DataFrame({
        "upz_code": latest["upz_code"].to_numpy(),
        "period": period,
        "level": [classes[i] for i in probabilities.argmax(axis=1)],
        "probability": probabilities.max(axis=1),
    })

    metrics = {
        "chosen_model": chosen,
        "model_names": MODEL_NAMES,
        "cv": cv,
        "test": test,
        "baseline_test": scores_only(baseline_test),
        "feature_importance": feature_importance(model, chosen),
        "cuts": list(cuts),
        "months": {"first": months[0].strftime("%Y-%m"), "last": months[-1].strftime("%Y-%m"),
                   "train": len(train_months), "test": len(test_months)},
        "period": period.isoformat(),
        "class_balance": {level: int((y == level).sum()) for level in LEVELS},
    }
    return TrainResult(model, chosen, config.as_dict(), metrics, predictions, len(rows))


def scores_only(result: dict) -> dict:
    return {k: result[k] for k in ("macro_f1", "recall_high", "accuracy")}