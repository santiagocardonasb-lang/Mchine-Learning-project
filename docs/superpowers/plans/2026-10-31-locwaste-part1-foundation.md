# LocWaste Part 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sketch with the LocWaste foundation: app structure, database, real Bogotá zones, accounts with roles, the approved visual design, a base map, and citizen reports.

**Architecture:** Flask app factory with blueprints for HTTP, a `services/` layer for logic, SQLAlchemy models, and an internal JSON API that small vanilla JS modules use to draw the Leaflet map. Geography is prepared once by a script into simplified GeoJSON plus a zone table; the geo service answers "which locality/UPZ/neighborhood is this point in".

**Tech Stack:** Python 3.13, Flask 3.1, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF, psycopg 3, shapely 2, python-dotenv, gunicorn, pytest; Leaflet 1.9.4; Plus Jakarta Sans; Bootstrap Icons.

**Spec:** `docs/superpowers/specs/2026-10-31-locwaste-design.md` (visual reference: `docs/superpowers/mockups/locwaste-v2/index.html`)

## Global Constraints

- Everything in English: code, UI copy, commits, docs.
- Comments only where they explain structure or a non-obvious decision; no restating code.
- Production DB is Supabase PostgreSQL through the **session pooler** URL in `DATABASE_URL`; local default is SQLite `instance/locwaste.db`.
- Nothing that must persist is written to disk at runtime (Render's disk is ephemeral).
- Public pages and public API responses never expose `user_id`, name or email of a reporter.
- Roles: `citizen` (default on registration) and `admin` (only via `flask create-admin`).
- Report enums: `waste_type` ∈ {household, construction_debris, bulky, organic, mixed}; `size` ∈ {small, medium, large}; `status` ∈ {open, in_progress, closed, rejected}; `source` ∈ {user, synthetic}.
- Map: Sumapaz (locality code 20) excluded; base tiles Esri World Light/Dark Gray Canvas.
- Palette and layout exactly as spec section 11 (tokens `--canvas #f5f6f2`, `--brand #2f6b5a`, risk `#5f9e7c / #d39a4f / #d9706a`, dark variants).
- Work happens on branch `P1-foundation`. Claude creates the files; Santiago runs every `git` command, so each "Commit" step means: stop, hand Santiago the file list and the commit message, wait for him.
- Part 2 and Part 3 files are not created here; the shared registration points are `app/__init__.py`, `app/templates/base.html` nav, `requirements.txt`.

## Review Focus

- A pin dropped outside urban Bogotá (or in Sumapaz) → `/api/geo/locate` returns 404 with a message and the report form refuses to submit. Test in Task 4 and Task 7.
- Registering `Ana@Mail.com` when `ana@mail.com` exists → rejected as duplicate (emails stored lowercase). Test in Task 5.
- A citizen opening `/admin` or any `role_required("admin")` view → 403, a guest → redirect to login. Test in Task 5.
- Public JSON (`/api/geo/*`, report lists shown publicly) contains no `user_id`/`email` keys. Test in Task 7.
- Supabase gives `postgres://…` or `postgresql://…` URLs → normalized to `postgresql+psycopg://…`; missing `DATABASE_URL` with `FLASK_ENV=production` → startup error naming the variable. Test in Task 1.

---

### Task 1: App factory, config and project skeleton

**Files:**
- Create: `config.py`, `wsgi.py`, `.env.example`, `app/__init__.py`, `app/extensions.py`, `app/blueprints/__init__.py`, `app/blueprints/main/__init__.py`, `app/blueprints/main/routes.py`, `tests/conftest.py`, `tests/test_config.py`
- Modify: `requirements.txt`, `.gitignore` (add `instance/`, `.env`, `.superpowers/`), `README.md`
- Delete: `app.py`, `content.py`, `templates/`, `static/` (sketch; its text moves to the About page in Task 6)

**Interfaces:**
- Produces: `create_app(config_name: str | None = None) -> Flask`; `config.get_config(name) -> type[Config]` with `Config`, `DevConfig`, `TestConfig`, `ProdConfig`; `config.normalize_db_url(url: str) -> str`; extensions `db`, `migrate`, `login_manager`, `csrf` in `app.extensions`; blueprint `main_bp` (name `"main"`) with endpoint `main.home` at `/`; pytest fixtures `app`, `client`, `db_session`.

- [ ] **Step 1: Write failing tests** in `tests/test_config.py`:
  `test_normalize_postgres_scheme` → `normalize_db_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"`;
  `test_normalize_postgresql_scheme` → same for `"postgresql://…"`; `test_sqlite_untouched`;
  `test_prod_requires_database_url` → with env `DATABASE_URL` unset, `create_app("production")` raises `RuntimeError` whose message contains `"DATABASE_URL"`;
  `test_home_responds` → `client.get("/").status_code == 200`.
- [ ] **Step 2: Run** `pytest tests/test_config.py -v` → FAIL (`ModuleNotFoundError: config`).
- [ ] **Step 3: Implement.** `requirements.txt` pins: Flask==3.1.3, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF, email-validator, psycopg[binary], shapely, python-dotenv, gunicorn==26.2.0, pytest (latest stable of each, pinned with `==`). `Config` reads `SECRET_KEY`, `DATABASE_URL` (default `sqlite:///<instance>/locwaste.db`), sets `SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True}`. `TestConfig`: `sqlite://`, `WTF_CSRF_ENABLED=False`, `TESTING=True`. `create_app` loads `.env` with python-dotenv, initializes extensions, registers `main_bp`. `wsgi.py`: `app = create_app()`. `main.home` renders a placeholder `"LocWaste"` string (replaced in Task 6).
- [ ] **Step 4: Run** `pytest -v` → all PASS.
- [ ] **Step 5: Commit** `chore: replace sketch with flask app factory and config`

### Task 2: Data model and migrations

**Files:**
- Create: `app/models/__init__.py`, `app/models/user.py`, `app/models/zone.py`, `app/models/report.py`, `app/models/model_run.py`, `migrations/` (via `flask db init`), `tests/test_models.py`

**Interfaces:**
- Produces: `User(id, name, email, password_hash, role, created_at)` with `set_password(raw)`, `check_password(raw) -> bool`, `is_admin` property, Flask-Login `UserMixin`; `Locality(id, code, name, population)`; `Upz(id, code, name, locality_id, critical_points, public_space_m2_per_inhabitant, area_km2)`; `Report(...)` per spec section 6 with `WASTE_TYPES`, `SIZES`, `STATUSES`, `SOURCES` tuples; `ModelRun(id, trained_at, trigger, n_rows, params: JSON, metrics: JSON, artifact: LargeBinary, is_active)`; `RiskPrediction(id, model_run_id, upz_id, period: Date, level, probability)`. All importable from `app.models`.

- [ ] **Step 1: Write failing tests:** `test_password_hashing` (`check_password("secret1")` True, `"wrong"` False, `password_hash != "secret1"`); `test_email_unique` (second user same email → `IntegrityError`); `test_report_defaults` (new report `status == "open"`, `source == "user"`, `reported_at` set); `test_report_rejects_unknown_waste_type` (SQLAlchemy `@validates` raises `ValueError` for `"plastic"`).
- [ ] **Step 2: Run** `pytest tests/test_models.py -v` → FAIL.
- [ ] **Step 3: Implement** models; enums as `String` columns validated with `@validates` against the tuples (portable across SQLite and PostgreSQL); indexes on `reports.upz_id`, `reports.reported_at`, `reports.status`.
- [ ] **Step 4: Run** `flask db init && flask db migrate -m "initial schema" && flask db upgrade` → creates `instance/locwaste.db`; `pytest -v` → PASS.
- [ ] **Step 5: Commit** `feat: add data model and initial migration`

### Task 3: Real Bogotá geography

**Files:**
- Create: `scripts/prepare_geo.py`, `data/raw/sector_catastral.geojson` (downloaded), `data/raw/locality_population.csv`, `data/zone_stats.csv`, `app/static/geo/localities.geojson`, `app/static/geo/upz.geojson`, `app/static/geo/neighborhoods.geojson`, `app/commands.py`, `tests/test_geo_data.py`
- Existing inputs: `data/raw/loca.json`, `data/raw/upz.json`, `data/raw/pc.geojson` (already downloaded)

**Interfaces:**
- Produces: GeoJSON files with properties — localities `{code, name}`; upz `{code, name, locality_code}`; neighborhoods `{code, name}`; `data/zone_stats.csv` columns `upz_code, upz_name, locality_code, locality_name, area_km2, critical_points, public_space_m2_per_inhabitant, collection_days_per_week`; CLI `flask load-zones` (idempotent upsert of `Locality` and `Upz` from the CSVs).

- [ ] **Step 1: Download** the cadastral sectors zip (URL in spec section 7) into `data/raw/` and unzip to `sector_catastral.geojson`; download the SDP population projection by locality and save `code,name,population,year,source_url` to `locality_population.csv`.
- [ ] **Step 2: Write failing tests** in `tests/test_geo_data.py` reading the generated files: 19 locality features and none with `code == "20"`; 112 UPZ features each with a non-empty `locality_code`; `zone_stats.csv` critical points sum to 478; every UPZ GeoJSON file under 1.5 MB.
- [ ] **Step 3: Run** `pytest tests/test_geo_data.py -v` → FAIL (files missing).
- [ ] **Step 4: Implement `scripts/prepare_geo.py`:** convert Esri `rings` to shapely polygons (`orient` + `make_valid`), drop locality 20, assign each UPZ its locality by largest intersection area, count UAESP points per UPZ with `contains`, parse `Frecuencia` into days per week (count weekday names; `"Lunes a Sabado"` = 6), area in km² via a local equal-area projection (multiply degree area by 111.32² · cos(4.6°)), simplify with `simplify(0.0003, preserve_topology=True)`, round coordinates to 5 decimals, write files. Implement `flask load-zones` in `app/commands.py` and register it in `create_app`.
- [ ] **Step 5: Run** `python scripts/prepare_geo.py && pytest -v && flask load-zones` → PASS; DB has 19 localities and 112 UPZ.
- [ ] **Step 6: Commit** `feat: prepare real bogota zones and load-zones command`

### Task 4: Geo service and geo API

**Files:**
- Create: `app/services/__init__.py`, `app/services/geo_service.py`, `app/blueprints/api/__init__.py`, `app/blueprints/api/geo.py`, `tests/test_geo_service.py`, `tests/test_api_geo.py`

**Interfaces:**
- Consumes: GeoJSON files from Task 3; `Locality`, `Upz`.
- Produces: `ZoneMatch` dataclass `(locality_code: str, locality_name: str, upz_code: str, upz_name: str, neighborhood: str | None)`; `geo_service.locate(lat: float, lon: float) -> ZoneMatch | None` (shapely `STRtree`, loaded once and cached); `geo_service.search_neighborhoods(q: str, limit: int = 8) -> list[dict]` returning `{name, lat, lon}` (case- and accent-insensitive prefix/substring match, centroid coords); `api_bp` (name `"api"`, prefix `/api`) with `GET /api/geo/localities`, `GET /api/geo/upz` (send the static files), `GET /api/geo/locate?lat=&lon=` → 200 `ZoneMatch` JSON or 404 `{"error": "Outside the covered area"}` or 400 for missing/non-numeric params, `GET /api/neighborhoods?q=`.

- [ ] **Step 1: Write failing tests:** `locate(4.6097, -74.0817)` (Plaza de Bolívar) → `locality_name == "Candelaria"` (compare case-insensitively); `locate(4.6280, -74.1630)` → locality `"Kennedy"`; `locate(4.0, -74.0)` → `None`; `search_neighborhoods("tintal")` non-empty and every name contains "tintal" ignoring case; API: locate outside → 404, `lat=abc` → 400, localities endpoint returns a FeatureCollection with 19 features.
- [ ] **Step 2: Run** `pytest tests/test_geo_service.py tests/test_api_geo.py -v` → FAIL.
- [ ] **Step 3: Implement** service and blueprint; register `api_bp` in `create_app`; exempt nothing from CSRF (all GET).
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Commit** `feat: add geo service and geo api`

### Task 5: Accounts and roles

**Files:**
- Create: `app/services/auth_service.py`, `app/forms/__init__.py`, `app/forms/auth.py`, `app/utils/__init__.py`, `app/utils/decorators.py`, `app/blueprints/auth/__init__.py`, `app/blueprints/auth/routes.py`, `app/templates/auth/login.html`, `app/templates/auth/register.html`, `tests/test_auth.py`
- Modify: `app/commands.py` (add `create-admin`), `app/__init__.py` (register `auth_bp`, `login_manager.user_loader`, `login_view = "auth.login"`)

**Interfaces:**
- Produces: `auth_service.register(name: str, email: str, password: str) -> User` (raises `EmailTaken`); `auth_service.authenticate(email: str, password: str) -> User | None`; `role_required(role: str)` decorator (guest → redirect to login, wrong role → 403); `auth_bp` endpoints `auth.register`, `auth.login`, `auth.logout` at `/auth/register`, `/auth/login`, `/auth/logout`; CLI `flask create-admin --email --name` (prompts for password, upgrades an existing user to admin).

- [ ] **Step 1: Write failing tests:** register then login redirects to `main.home` and session has user; `register("Ana", "Ana@Mail.com", …)` after `"ana@mail.com"` raises `EmailTaken`; wrong password → login page shows `"Invalid email or password"`; password shorter than 8 → form error; a test-only route decorated with `role_required("admin")`: guest → 302 to `/auth/login`, citizen → 403, admin → 200; `create-admin` via `app.test_cli_runner()` creates a user with `role == "admin"`.
- [ ] **Step 2: Run** `pytest tests/test_auth.py -v` → FAIL.
- [ ] **Step 3: Implement** forms (`RegisterForm`: name, email, password ≥ 8, confirm; `LoginForm`: email, password, remember), service (emails `strip().lower()`), routes with `next` redirect limited to relative URLs, templates as plain markup (styled in Task 6).
- [ ] **Step 4: Run** `pytest -v` → PASS.
- [ ] **Step 5: Commit** `feat: add registration, login and roles`

### Task 6: Design system, layout and content pages

**Files:**
- Create: `app/static/css/tokens.css`, `app/static/css/app.css`, `app/static/js/theme.js`, `app/templates/base.html`, `app/templates/partials/nav.html`, `app/templates/partials/flash.html`, `app/templates/main/home.html`, `app/templates/main/about.html`, `app/templates/main/how_it_works.html`, `app/content.py`, `tests/test_pages.py`
- Modify: `app/blueprints/main/routes.py`, `app/templates/auth/*.html` (use the card style of the mockup's sign-in view)

**Interfaces:**
- Consumes: `Report`, `Upz`, `RiskPrediction` (counts only).
- Produces: `base.html` blocks `title`, `content`, `scripts`, and a `nav_links` block Part 2/3 extend; CSS classes from the mockup (`card`, `btn btn-brand|btn-soft|btn-ghost`, `pill low|medium|high`, `label`, `chip`, `choice`, `check`, `stepper`); routes `main.home` (`/`), `main.about` (`/about`), `main.how_it_works` (`/how-it-works`); `app/content.py` holding the About text (title, problem statement, research question, general objective) and How-it-works copy.

- [ ] **Step 1: Write failing tests:** `/`, `/about`, `/how-it-works` return 200; home contains `"Know where waste"` and links to `/reports/new` and `/map`; about contains `"General objective"`; nav shows "Sign in" for guests and "Sign out" for a logged-in user; home "Reports this month" shows the real count of non-rejected reports of the current month.
- [ ] **Step 2: Run** `pytest tests/test_pages.py -v` → FAIL.
- [ ] **Step 3: Implement** by porting the mockup v2: tokens and dark theme to `tokens.css`, components to `app.css`, theme toggle persisted in `localStorage` (`theme.js`, applied before paint in `<head>`). Home: hero, three steps, preview map (static, non-interactive; uses Task 4 GeoJSON), priority zones section that shows "Predictions appear after the first model run" when there is no active `RiskPrediction`.
- [ ] **Step 4: Run** `pytest -v` → PASS; open `/` in the browser in light and dark and compare with the mockup.
- [ ] **Step 5: Commit** `feat: add design system, layout and content pages`

### Task 7: Base risk map and citizen reports

**Files:**
- Create: `app/services/report_service.py`, `app/forms/report.py`, `app/blueprints/reports/__init__.py`, `app/blueprints/reports/routes.py`, `app/blueprints/map/__init__.py`, `app/blueprints/map/routes.py`, `app/templates/map/index.html`, `app/templates/reports/new.html`, `app/static/js/map.js`, `app/static/js/report_form.js`, `tests/test_reports.py`

**Interfaces:**
- Consumes: `geo_service.locate`, `Report`, `role_required` not needed (login only).
- Produces: `report_service.create(user: User, lat: float, lon: float, waste_type: str, size: str, has_rodents: bool, has_insects: bool, has_odor: bool, near_water: bool, description: str | None) -> Report` (raises `OutsideCoverage` when `locate` is `None`; fills locality, UPZ, neighborhood); `report_service.public_dict(report: Report) -> dict` (keys: id, latitude, longitude, locality, upz, neighborhood, reported_at, waste_type, size, status — no user fields); `report_service.on_created` hook list (empty here; Part 2 appends the auto-retrain trigger); endpoints `map.index` (`/map`), `reports.new` (`/reports/new`, login required); JS `initRiskMap(el, options)` exported from `map.js` so Part 3 adds heat and risk layers to the same map.

- [ ] **Step 1: Write failing tests:** logged-in POST to `/reports/new` with Kennedy coordinates creates a report with `upz_id` set and `source == "user"`, redirects to `map.index` and flashes `"Report sent"`; POST with `lat=4.0, lon=-74.0` → no report created and page shows `"outside the covered area"`; guest GET `/reports/new` → 302 to login; `public_dict` has no `user_id`, `name` or `email` keys; `/map` returns 200 for guests.
- [ ] **Step 2: Run** `pytest tests/test_reports.py -v` → FAIL.
- [ ] **Step 3: Implement.** Map page: full-screen layout of the mockup with the top bar holding the locality select (fit bounds) — the neighborhood search box and "My reports" belong to Part 3 — summary panel, legend; boundaries from `/api/geo/upz` and `/api/geo/localities` with locality labels; UPZ fill neutral until Part 3 adds risk. Report page: stepper, Leaflet map with movable pin, on move call `/api/geo/locate` and fill the zone chips (show the error chip and disable submit on 404), icon choices for type and size, check tiles, note; hidden `latitude`/`longitude` fields; "Report here" accepts `?lat=&lon=` to preset the pin.
- [ ] **Step 4: Run** `pytest -v` → PASS; in the browser, register, report a point in Kennedy, see the "Report sent" message on the map.
- [ ] **Step 5: Commit** `feat: add base risk map and citizen reports`

### Task 8: Supabase and Render

**Files:**
- Modify: `README.md` (run locally, env vars, commands), `.env.example`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1:** In Supabase create the project and copy the **session pooler** URI into a local `.env` as `DATABASE_URL`; run `flask db upgrade && flask load-zones && flask create-admin --email <admin email> --name Admin`. Expected: tables exist in Supabase, 19 localities, 112 UPZ.
- [ ] **Step 2:** In Render (`limpia-waste` service) set env vars `DATABASE_URL`, `SECRET_KEY`, `FLASK_ENV=production`; start command `gunicorn wsgi:app`; build command `pip install -r requirements.txt && flask db upgrade`.
- [ ] **Step 3: Verify** the deployed URL: `/` 200, `/map` draws Bogotá, register a user, submit a report and see "Report sent"; `pytest -v` locally all PASS.
- [ ] **Step 4: Commit** `docs: document setup, environment and deployment`
