# CRISP-ML(Q) evidence

LocWaste follows CRISP-ML(Q) (Studer et al., 2021). For each of the six phases this page lists
what was done, where it is in the repository, the commits that built it and the result that shows
it works. Commits link to their changes on GitHub; metrics are from the active production run
(Run 2, trained 2026-11-16).

## 1. Business and data understanding

- **Goal:** send collection and prevention to the zones where waste will accumulate next month.
- **ML question:** classify each UPZ's next-month report rate as low, medium or high.
- **Success criteria:** macro-F1 and recall of the high class above the most-frequent baseline;
  accuracy is reported but not used to choose.
- **Data:** SDP localities and population projections, DADEP UPZ and public space indicator, UAECD
  cadastral sectors, 478 active UAESP critical points (Datos Abiertos Bogotá).
- **Quality assurance:** missing open data (UPZ population, rivers) documented as assumptions.

| Evidence | Where |
|---|---|
| Design and success criteria | `docs/superpowers/specs/2026-10-31-locwaste-design.md` |
| Open data and its preparation | `data/raw/`, `scripts/prepare_geo.py`, `data/zone_stats.csv` |
| Commits | b170339, 9959ea5, 0f1c28f |

## 2. Data engineering

- Reports are placed in their locality, UPZ and neighborhood from the pin (`app/services/geo_service.py`).
- 24 months of synthetic history (17,771 reports, seed 42) calibrated on the real critical points,
  density and public space, stored with `source = synthetic` (`ml/synthetic.py`).
- One row per UPZ and complete UTC month: 2,576 zone-months with rates, lags, trends and shares
  (`ml/features.py`). Rejected reports are excluded.
- Target: next month's rate per 10,000 inhabitants in terciles fit on the training months only.
- **Quality assurance:** tests for leakage, complete months and calibration.

| Evidence | Where |
|---|---|
| Code | `ml/synthetic.py`, `ml/features.py`, `app/services/geo_service.py` |
| Tests | `tests/test_synthetic.py`, `tests/test_features.py`, `tests/test_geo_service.py` |
| Commits | 6f1b95c, f93858e, b01ad30, 0f75145, 276e7f6 |

## 3. Model engineering

- Most-frequent baseline, logistic regression (C = 1.0) and random forest (300 trees, depth 8,
  min 5 samples per leaf), balanced class weights.
- All parameters in `ml/config.py`; every run stored as a version in `model_runs` with its
  parameters, metrics and joblib artifact; old artifacts are pruned.
- **Quality assurance:** fixed seed, pinned dependencies, parameters visible on `/model`.

| Evidence | Where |
|---|---|
| Code | `ml/config.py`, `ml/train.py`, `app/services/training_service.py` |
| Tests | `tests/test_train.py`, `tests/test_training_service.py`, `tests/test_config.py` |
| Commits | b3dc945, 2eac1a2, 44b10d1, 9c93aa2 |

## 4. Model evaluation

- Temporal hold-out of the last 20% of months and 5-fold `TimeSeriesSplit` on the rest.
- Cross-validated macro-F1: random forest 0.571 ± 0.009, logistic regression 0.555 ± 0.019,
  baseline 0.156 ± 0.022.
- Test: random forest macro-F1 0.554 vs 0.168 for the baseline; recall of the high class 0.58.
- Confusion matrix (rows actual low, medium, high): [[120, 65, 12], [48, 86, 54], [12, 61, 102]];
  errors fall mostly between neighboring levels.
- Top features: current report rate (0.31), critical points (0.10), population density (0.09).
- **Quality assurance:** model chosen by CV macro-F1 then high-class recall; error analysis shown
  on `/model`.

| Evidence | Where |
|---|---|
| Code | `ml/train.py`, `app/templates/model/index.html` |
| Commits | 2eac1a2, 2c453a7 |

## 5. Deployment

- Flask app on Render (`gunicorn wsgi:app`), PostgreSQL on Supabase, migrations applied on every
  build. The `ml` package has no Flask code, so training and serving share the features.
- Roles: citizens report and consult; admins moderate, manage users, retrain and manage priorities.
- Batch inference: every run predicts all UPZ (`risk_predictions`) and creates collection tasks
  for high-risk ones. On-demand inference: `/risk-check` for one UPZ.
- **Quality assurance:** CSRF on every form, hashed passwords, role checks on the server, secure
  cookies in production, friendly error page.

| Evidence | Where |
|---|---|
| Code | `app/__init__.py`, `app/blueprints/`, `app/services/inference_service.py`, `app/services/collection_service.py` |
| Tests | `tests/test_access.py`, `tests/test_auth.py`, `tests/test_inference.py`, `tests/test_collection.py` |
| Commits | 9218ad4, cf381de, 3cb1b4b, 7331e78, d57444f, 7ac6b63, 89b5c52, 145f005 |
| Published app | https://limpia-waste.onrender.com |

## 6. Monitoring and maintenance

- `app_events` logs requests, latency and errors (30-day retention, `prune-events`);
  `inference_logs` logs every prediction with user, model version, result and duration.
- `/admin/monitoring`: outcomes of predicted months, drift (PSI of the report rate > 0.2, share
  shift > 10 points) and performance (live macro-F1 < 80% of CV) with a retraining recommendation.
  Production PSI on 2026-11-16: 0.092, no drift.
- Retraining from the app and automatically after 50 new citizen reports.
- Help and feedback tickets answered by admins.

| Evidence | Where |
|---|---|
| Code | `app/services/monitoring_service.py`, `app/services/feedback_service.py` |
| Tests | `tests/test_monitoring.py`, `tests/test_feedback.py`, `tests/test_operations_models.py` |
| Commits | 80d8496, e9a83ea, 6208669 |
| Design | `docs/superpowers/specs/2026-11-15-operations-design.md` |

## Reference

Studer, S., Bui, T. B., Drescher, C., Hanuschkin, A., Winkler, L., Peters, S., & Müller, K.-R.
(2021). Towards CRISP-ML(Q): A machine learning process model with quality assurance methodology.
*Machine Learning and Knowledge Extraction, 3*(2), 392–413. https://doi.org/10.3390/make3020020
