# LocWaste — Design

Date: 2026-10-31 · Status: approved by Santiago (2026-10-31) · Methodology: CRISP-DM

## 1. Intent

LocWaste is a Flask web app where registered citizens report places in Bogotá where solid waste
accumulates. Reports, together with an initial synthetic history calibrated on real open data,
feed a Machine Learning model that classifies each UPZ (urban planning zone) by its risk of waste
accumulation next month. The result is shown on a map of Bogotá — localities, UPZ, a heat map of
reports and risk labels — so anyone can see the whole city or focus on one locality or
neighborhood.

It is a graded university Machine Learning project, built by a team of three in ordered parts
and defended orally. It must look clean, organized and easy to use, and the ML work must be
visible and defensible.

## 2. Goals, non-goals, anti-goals

**Goals**
- Registration and login for many users, with two roles: `citizen` and `admin`.
- Report a waste accumulation point at any time by clicking on the map.
- Map of Bogotá with locality and UPZ boundaries, a heat map of reports, risk colors per UPZ and
  labels; filter by locality and search by neighborhood.
- A realistic synthetic dataset (24 months) so the model gives useful results from day one.
- A risk classifier (low / medium / high per UPZ, next month), retrained manually by an admin and
  automatically after enough new reports.
- Pages that document the CRISP-DM phases and the model's parameters, metrics and comparison.

**Non-goals**
- Estimating tonnage, optimizing collection routes, or guaranteeing accumulation is prevented.
- Photo uploads, email verification, password reset by email, notifications.
- A separate frontend app or a mobile app.

**Anti-goals** (failure even if it works)
- A cluttered, colorful UI. Color is only a signal.
- Data leakage: the target built from the same-period values used as predictors.
- Hidden model parameters or a one-split comparison (the professor penalized both before).
- Exposing who reported a point on the public map.
- Over-commented or speculative code.

## 3. Constraints

- **Stack:** Python 3.13, Flask with Jinja templates, as in the team's previous ML project.
- **Database:** Supabase PostgreSQL in production (as in the Carpool project), SQLite locally.
  Connection through `DATABASE_URL` in `.env`.
- **Hosting:** Render free tier. The disk is ephemeral, so nothing that must persist (users,
  reports, trained models) may live on disk.
- **Language:** everything in English — code, UI, content, commits, docs.
- **Repository:** `santiagocardonasb-lang/Mchine-Learning-project`, one branch per part, merged by
  pull request in order, branches kept as evidence.
- **Team:** Part 1 Santiago (files created directly), Parts 2 and 3 Holman and Jhon (delivered as
  step-by-step guides). No two parts edit the same file except the shared registration points
  listed in section 11.
- **Grading:** key parameters written in the model file and rendered with their real values;
  cross-validation with mean ± std; comparison against a baseline; written error analysis.

## 4. Approaches

| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | Flask + Jinja pages, Leaflet map, internal JSON API (`/api/...`) consumed by small vanilla JS modules | One project, one deploy, same structure the course already knows; map interactivity needs some JS |
| B | Flask REST API + React frontend (like Carpool) | Modern, but two projects, two deploys, roughly double the code, and the ML part drifts from the course pattern |
| C | Flask + Folium maps rendered on the server | Fast to start, but click-to-report and filtering without reloads become awkward |

Chosen by Santiago: **A**.

## 5. Architecture

```
Mchine-Learning-project/
├── wsgi.py                      # gunicorn entry: app = create_app()
├── config.py                    # Config / DevConfig / TestConfig from env vars
├── requirements.txt  .python-version  .env.example
├── app/
│   ├── __init__.py              # create_app(): extensions, blueprints, CLI commands
│   ├── extensions.py            # db, migrate, login_manager, csrf
│   ├── models/                  # SQLAlchemy models (section 6)
│   ├── services/                # business logic, no Flask request objects
│   │   ├── auth_service.py      # register, authenticate
│   │   ├── geo_service.py       # point → locality / UPZ / neighborhood; GeoJSON access
│   │   ├── report_service.py    # create, list, change status, heat-map points
│   │   ├── risk_service.py      # current risk per UPZ for the map
│   │   └── training_service.py  # run training, store ModelRun, auto-retrain trigger
│   ├── blueprints/
│   │   ├── main/                # home, about, crisp-dm
│   │   ├── auth/                # register, login, logout
│   │   ├── reports/             # new report, my reports
│   │   ├── map/                 # map page
│   │   ├── model/               # model metrics page
│   │   ├── admin/               # report queue, users, retrain
│   │   └── api/                 # JSON for the map
│   ├── forms/                   # Flask-WTF forms
│   ├── utils/decorators.py      # role_required("admin")
│   ├── templates/               # base.html, partials/, one folder per blueprint
│   └── static/
│       ├── css/                 # tokens.css (design system), app.css
│       ├── js/                  # map.js, report_form.js, theme.js
│       └── geo/                 # simplified GeoJSON: localities, upz, neighborhoods
├── ml/                          # independent of Flask; importable by training_service
│   ├── config.py                # all model parameters (visible, rendered on the model page)
│   ├── features.py              # reports → UPZ × month table, lags, target
│   ├── train.py                 # baseline + models, temporal CV, metrics
│   └── synthetic.py             # synthetic dataset generator
├── data/
│   ├── raw/                     # downloaded open data (section 7)
│   ├── zone_stats.csv           # real per-UPZ attributes used by the generator and features
│   └── synthetic_reports.csv    # generated, committed, seeded into the DB
├── scripts/prepare_geo.py       # Esri JSON → simplified GeoJSON + zone_stats.csv
├── migrations/
└── tests/
```

**Layering rule:** blueprints handle HTTP and forms only; services hold the logic and talk to
models; `ml/` never imports Flask. This is what lets the three parts be built in order without
stepping on each other.

**Extensions:** Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF (CSRF on every form and
on JSON POSTs), `psycopg[binary]`, shapely, pandas, numpy, scikit-learn, joblib, python-dotenv,
gunicorn, pytest.

**CLI commands** (registered in `create_app`): `flask create-admin`, `flask seed-synthetic`,
`flask train`.

## 6. Data model

| Table | Fields |
|---|---|
| `users` | id, name, email (unique), password_hash, role (`citizen`/`admin`), created_at |
| `localities` | id, code, name, population |
| `upz` | id, code, name, locality_id, critical_points (real UAESP count), public_space_m2_per_inhabitant |
| `reports` | id, user_id (nullable for synthetic), latitude, longitude, locality_id, upz_id, neighborhood, reported_at, waste_type, size, has_rodents, has_insects, has_odor, near_water, description, status, source (`user`/`synthetic`), updated_at |
| `model_runs` | id, trained_at, trigger (`manual`/`auto`/`cli`), n_rows, params (JSON), metrics (JSON), artifact (binary, joblib), is_active |
| `risk_predictions` | id, model_run_id, upz_id, period (first day of month), level, probability |

- `waste_type`: `household`, `construction_debris`, `bulky`, `organic`, `mixed`.
- `size`: `small` (a few bags), `medium` (a pile), `large` (blocks the sidewalk or street).
- `status`: `open` → `in_progress` → `closed`; `rejected` for spam or duplicates. Only
  `rejected` reports are excluded from training and the heat map.
- The trained model is stored in `model_runs.artifact` because Render's disk is wiped.

## 7. Data sources (real, public)

| Use | Dataset | Publisher | Verified |
|---|---|---|---|
| Locality boundaries | [Localidad. Bogotá D.C.](https://datosabiertos.bogota.gov.co/dataset/localidad-bogota-d-c) | SDP | 20 localities, Esri JSON |
| UPZ boundaries + public space indicator | [Indicador espacio público UPZ](https://datosabiertos.bogota.gov.co/dataset/indicador-espacio-publico-upz) | DADEP | 112 UPZ, Esri JSON, effective public space m²/inhabitant |
| Neighborhood names and shapes | [Sector catastral](https://datosabiertos.bogota.gov.co/dataset/sector-catastral) | UAECD | GeoJSON |
| Calibration of the synthetic data | [Puntos críticos arrojo clandestino](https://datosabiertos.bogota.gov.co/dataset/puntos-criticos-arrojo-clandestino-residuos-bogota-d-c) | UAESP | 478 active points with locality and collection frequency |
| Locality population | SDP population projections by locality | SDP | to be cited when loaded |

`scripts/prepare_geo.py` converts the Esri JSON to GeoJSON, simplifies geometries so the map
loads fast, and writes `data/zone_stats.csv` (per UPZ: locality, real critical points, public
space indicator, area, collection days per week of nearby critical points).

## 8. Synthetic dataset

Generated by `ml/synthetic.py` with a fixed seed, 24 months (Nov 2024 – Oct 2026), output
`data/synthetic_reports.csv`, loaded by `flask seed-synthetic` with `source = synthetic`.

Monthly expected reports per UPZ = base × seasonality × noise, where:
- **base** grows with the real UAESP critical points in the UPZ, the locality population density,
  and low public space per inhabitant; UPZ with no critical points still get a small base.
- **seasonality** rises in Bogotá's rainy months (April–May, October–November).
- **persistence:** a UPZ that had many reports last month tends to stay high (autocorrelation),
  which is what makes next-month prediction learnable.
- Each report gets a point inside the UPZ (biased toward real critical points), and attributes
  drawn from distributions that depend on the zone (e.g. `construction_debris` more frequent where
  UAESP points concentrate, `near_water` more likely in UPZ crossed by rivers).

The generator's assumptions are listed on the CRISP-DM page so the data origin is stated.

## 9. Machine Learning

**Unit:** one row per UPZ × month.

**Features (month t):** report count, lags t-1..t-3, 3-month rolling mean, month-over-month
change, share of `large` reports, share with vectors (rodents/insects/odor), share `near_water`,
open reports at month end, month of year, real critical points, public space indicator,
locality population density.

**Target:** risk level of month **t+1**, from the next month's report count per 10,000 inhabitants
split into terciles (`low` / `medium` / `high`). Tercile cut points are computed on the training
months only. Features use only data up to month t, so the target is never built from the
predictors' own period.

**Models:** `DummyClassifier` (most frequent), logistic regression, random forest. Chosen model by
macro-F1 and `high`-class recall, not accuracy.

**Validation:** temporal hold-out (last 20% of months as test) plus `TimeSeriesSplit` with 5 folds,
reported as mean ± std. `class_weight="balanced"`.

**Visible parameters:** every value (`TEST_MONTHS_FRACTION`, `N_SPLITS`, `RANDOM_STATE`,
`N_ESTIMATORS`, `MAX_DEPTH`, `AUTO_RETRAIN_THRESHOLD`, …) lives in `ml/config.py` and the model page
renders the stored `model_runs.params` of the active run.

**Retraining**
- Manual: admin presses "Retrain" → `training_service.run(trigger="manual")`.
- Automatic: after each new report, if non-rejected user reports created since the last run reach
  `AUTO_RETRAIN_THRESHOLD` (default 50), training starts in a background thread so the user is not
  kept waiting.
- Each run stores params, metrics, artifact and the next-month predictions; the newest successful
  run becomes active.

**Model page:** parameters, metrics per class, confusion matrix, CV mean ± std per model vs. the
baseline, feature importance, a written reading of the errors, and the history of runs.

## 10. Screens

| Route | Who | Content |
|---|---|---|
| `/` | everyone | purpose headline, CTAs, map preview, three steps, top priority zones (section 11) |
| `/map` | everyone | full map: locality + UPZ boundaries, heat map, risk colors, labels, locality filter, neighborhood search, time range |
| `/reports/new` | logged in | map to drop a pin (locality/UPZ/neighborhood filled automatically) + form fields |
| `/reports/mine` | logged in | own reports and their status |
| `/auth/register`, `/auth/login` | guests | forms |
| `/admin` | admin | report queue with status changes, users and roles, retrain button, last runs |
| `/model` | everyone | section 9 model page |
| `/crisp-dm` | everyone | the six phases applied to LocWaste, data sources, synthetic assumptions |
| `/about` | everyone | project title, problem statement, general objective (from the sketch) |

**API** (JSON): `/api/geo/localities`, `/api/geo/upz`, `/api/geo/locate?lat=&lon=`,
`/api/neighborhoods?q=`, `/api/heatmap?locality=&months=`, `/api/risk`. Public responses never
include `user_id`.

**Map:** Leaflet with `leaflet.heat`; base tiles Esri World Light Gray / Dark Gray Canvas (CARTO's
free basemaps now show an "API key required" watermark). Sumapaz (rural locality 20) is left out
of the urban map.
Layers can be toggled: heat map, UPZ risk fill, boundaries. Labels: UPZ name, risk level and
report count on hover; locality names at low zoom. "Detailed but not excessive": neighborhoods are
searchable and shown as a highlighted outline when selected, not drawn all at once.

## 11. Visual identity

Approved with mockup v2 (2026-10-31). Structure and ordering come from the "Kinetic Mono" system of
Santiago's Carpool and Scanner apps (function-named tokens, cards, small uppercase labels, light and
dark themes); the palette is softer:
- Light: canvas `#f5f6f2` (warm off-white), surface `#fff`, subtle `#eef0ea`, line `#e2e5dc`,
  text `#1f2a26` / `#5b6660` / `#8a948e`.
- Brand sage green `#2f6b5a` with soft `#e3efe9` for primary actions, active nav and chips.
- Risk in pastel tones, each with a soft background: low `#5f9e7c`, medium `#d39a4f`,
  high `#d9706a`. Heat-map gradient `#cfe5d6 → #f1c98f → #e98f86 → #d9706a`.
- Dark theme redefines the same tokens (canvas `#141816`, brand `#7cc2a9`, lighter risk tones).
- Font Plus Jakarta Sans; 18px card radius, soft layered shadows; Bootstrap Icons.
- Tokens live in `tokens.css`, redefined under `html.dark`; theme choice saved in `localStorage`.
- Recycle icon in a soft rounded square as the brand mark.

**Approved layout**
- Nav: Home · Risk map · Model · How it works; theme toggle, Sign in, and a primary
  "Report waste" button always visible.
- Home explains the purpose first: headline, one-sentence flow, two CTAs (report / explore),
  a live preview of the real map, three steps (Report → See the hotspots → Anticipate the risk),
  and the top five priority zones.
- Risk map is full screen with floating cards: search + locality + period on top, a small summary
  panel on the left (stats, top priority, layer toggles), a zone detail card on the right when a UPZ
  is clicked (risk, reports, most common type, vectors share, open reports, "Report here"), legend
  bottom right.
- Report is a stepper (Location → What you see → Send): map with a movable pin, detected zone
  chips, large icon choices for type and size, check tiles for vectors and water, optional note.

The mockup is the visual reference for every part: `docs/superpowers/mockups/locwaste-v2/`
(open `index.html`). Part 1 recreates it in the Flask templates.

## 12. Team split (ordered)

| Part | Owner | CRISP-DM | Delivers |
|---|---|---|---|
| **1 — Foundation** | Santiago | 1, 2 | project structure, config, Supabase/SQLite, all models and migrations, auth and roles, design system and base layout, `prepare_geo.py` + GeoJSON + `zone_stats.csv`, geo service and API, base map with boundaries, report form, my reports, about page, `create-admin` |
| **2 — Data and model** | teammate | 3, 4, 5 | `ml/` (synthetic, features, train, config), `seed-synthetic` and `train` commands, `training_service` with manual and auto retrain, model page, CRISP-DM page |
| **3 — Results** | teammate | 6 | heat map and risk layers, labels, filters and neighborhood search, `risk_service`, admin panel, home stats |

Shared files each later part touches only to register its own pieces: `app/__init__.py`
(blueprints, commands), `base.html` (nav links), `requirements.txt`.

**Accounts and environments.** Supabase and Render belong to Santiago's accounts, so every
operation on them is his, whichever part it serves: creating the database, running migrations
and `load-zones` / `seed-synthetic` / `train` / `create-admin` against Supabase, setting
environment variables, and deploying. Teammates work only locally with SQLite and never need
those credentials; each part's guide ends with the steps Santiago runs in production.

## 13. Testing

pytest with an in-memory SQLite config, on what breaks silently: registration/login and the admin
guard; a report gets the right UPZ from its coordinates; public API hides `user_id`; features use
no future data and the target is next month; a training run stores metrics for the baseline and
both models.

## 14. Calls made by the designer

- Supabase is reached through its **session pooler** connection string (IPv4), since the direct
  host is IPv6-only and Render's free tier connects over IPv4.
- `neighborhood` on a report is the name of the cadastral sector containing the point.
- The synthetic history totals roughly 18,000 reports (about 750 per month citywide), scaled so
  the busiest UPZ match the real UAESP concentration.
- Before the first training run the map shows boundaries and the heat map, and UPZ risk as
  "no prediction yet".
- Locality population comes from SDP projections; the exact table is cited on the CRISP-DM page.

## 15. Left to the builder

Exact copy text, spacing values, form validation messages, migration details, the simplification
tolerance for GeoJSON, and the precise distributions of the synthetic generator within the rules
of section 8.
