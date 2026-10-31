# Handoff — Part 1 → Parts 2 and 3

Part 1 (Foundation) is merged into `master` and deployed. This note lists what Parts 2 and 3
must know so they build on it without breaking it. The spec is
`docs/superpowers/specs/2026-10-31-locwaste-design.md`.

## Rules for every part

- Work locally with SQLite only. Supabase and Render belong to Santiago: every production step
  (migrations, `seed-synthetic`, `train`, environment variables, deploys) is listed at the end of
  each guide and run by him.
- Touch Part 1 files only at the registration points: `app/__init__.py` (blueprints, commands),
  the `nav_links` block in `app/templates/base.html`, and `requirements.txt` (pinned with `==`).
- Everything in English. Run `pytest` before every commit; Part 1 ships with 99 passing tests.

## Part 2 — Data and model

- **Dates:** SQLite returns naive datetimes, PostgreSQL returns aware ones. Normalise every
  `reported_at` to UTC before grouping by month. Months are UTC calendar months
  (same rule as `app/services/stats_service.py`).
- **Seeding:** insert synthetic reports through the ORM (or validate against `Report.WASTE_TYPES`,
  `SIZES`, `STATUSES`, `SOURCES`); bulk inserts skip the model validators. Use `source="synthetic"`
  and `user_id=None`.
- **Zone attributes:** `collection_days_per_week` lives only in `data/zone_stats.csv`, not in the
  `upz` table. `ml/` must not import Flask, so read it from the CSV.
- **Population:** only per locality (`localities.population`, SDP 2026). The "reports per 10,000
  inhabitants" target needs a stated rule to split locality population across its UPZ
  (for example, by UPZ area — `upz.area_km2`).
- **Auto-retrain hook:** append it to `app.services.report_service.on_created` once, at module
  import, not inside `create_app` (tests would stack hooks). The hook receives the saved report;
  pass `report.id` (not the ORM object) to any background thread and give the thread its own app
  context. Part 1 already isolates hook failures and rolls back the session, so a failing hook
  never breaks a saved report.
- **Predictions:** store runs in `model_runs` (artifact in the `artifact` column, not on disk) and
  predictions in `risk_predictions`. Add a unique constraint on
  `(model_run_id, upz_id, period)` in your own migration if you need it.
- **Pages:** add the "Model" nav link through the `nav_links` block.

## Part 3 — Results

- **Map layers:** `app/templates/map/index.html` exposes the map as `window.locwasteMap`
  (`{map, layers, ready}` from `initRiskMap`) and an empty `{% block map_layers %}` after it.
  Add the heat map and risk fill there by extending the template, not by editing it.
- **Home:** an empty `{% block home_stats %}` is ready in `app/templates/main/home.html`.
  `stats_service.reports_this_month()` counts only citizen reports (`source == "user"`).
- **Moved to Part 3:** the "My reports" page (`/reports/mine`) and the neighborhood search box on
  the map, which uses `/api/neighborhoods?q=`.
- **Public data:** use `report_service.public_dict(report)` for anything public; it never exposes
  the reporter. It lazy-loads locality and UPZ per report, so join-load them when listing many.
- **Admin:** guard views with `app.utils.decorators.role_required("admin")`.
- **Accessibility:** use the `--low-ink`, `--medium-ink`, `--high-ink` tokens for risk text and
  keep `--low`, `--medium`, `--high` for fills, swatches and dots.
