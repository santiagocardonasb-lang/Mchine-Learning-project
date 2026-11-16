# LocWaste

Flask web app where citizens report waste accumulation points in Bogotá. A machine learning
model predicts waste-accumulation risk per zone and shows it on a map. Built with the CRISP-DM
methodology; see `docs/superpowers/specs/2026-10-31-locwaste-design.md`.

## Run locally

```
python -m venv .venv
.venv\Scripts\activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # macOS/Linux: cp .env.example .env
flask --app wsgi db upgrade
flask --app wsgi load-zones
flask --app wsgi run
```

Without `DATABASE_URL` the app uses a local SQLite file in `instance/`. Keep the production
database URL out of your local `.env`, so local runs never write to production.

Run the tests with `pytest`.

## Commands

| Command | What it does |
|---|---|
| `flask --app wsgi db upgrade` | Applies the database migrations |
| `flask --app wsgi load-zones` | Loads the 19 localities and 112 UPZ (safe to run again) |
| `flask --app wsgi create-admin --email <email> --name <name>` | Creates an admin, or promotes an existing user and resets the password |
| `python scripts/prepare_geo.py` | Rebuilds the GeoJSON files and `data/zone_stats.csv` from the open data in `data/raw/` |

## Using the model in operations

See `docs/superpowers/specs/2026-11-15-operations-design.md` for the decisions behind these pages.

- **Risk check** (`/risk-check`, any signed-in user): pick a UPZ, or press "Check risk now" on the
  map's zone card or "Check this zone's risk" in My reports. The active model predicts next
  month's level and class probabilities from that zone's stored reports, with the same features
  as training, and the page explains the result, how to use it and its limitations.
- **Inference history** (`/inferences`): every prediction with its user, model run, zone, result,
  duration and status. Users see their own risk checks; admins see all of them plus the batch
  prediction of each training run.
- **Collection priorities** (`/admin/priorities`, admins): each training run creates a pending
  task for every high-risk UPZ that has no task yet for that month (done or dismissed ones
  are not reopened by a later run). A pending task stays open if a retrain in the same month
  no longer rates its UPZ as high risk; review or dismiss it by hand. Schedule a collection date,
  mark it done (optionally closing the zone's open citizen reports) or dismiss it with a note. The
  pending count is shown on the app home and the Admin page.
- **Monitoring** (`/admin/monitoring`, admins): requests and average response time, risk checks
  and their latency, errors and the active model's age over the last 7 days; accuracy, macro F1
  and confusion matrix of every predicted month that is complete; a drift check (PSI of the
  report rate and the shift in waste type, size and vector shares) and a performance check (live
  macro F1 against the cross-validation score). Thresholds live in `ml/config.py`
  (`DRIFT_PSI_THRESHOLD`, `DRIFT_SHARE_THRESHOLD`, `PERFORMANCE_DROP_FRACTION`); any flag shows a
  retraining recommendation with a "Retrain now" button.

Every app request (static files excluded) and every unhandled error is stored in `app_events`;
an error shows a friendly page instead of a stack trace.

## Help and feedback procedure

1. Any signed-in user opens **Help & feedback** (the question mark in the menu). The page they
   came from is attached to the ticket.
2. They choose the kind — **incident** (something stopped working or data looks wrong), **bug**
   (unexpected behaviour) or **suggestion** — describe it and send it. The ticket starts **open**
   and appears under "My tickets".
3. An admin reviews it in **Admin → Feedback**, sets it to **in review** while working on it and
   to **resolved** with an answer.
4. The user sees the status and the answer under "My tickets".

## Environment variables

| Variable | Local | Production (Render) |
|---|---|---|
| `SECRET_KEY` | optional | required — `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | optional (SQLite by default) | required — Supabase **session pooler** URI (port 5432) |
| `FLASK_ENV` | `development` | `production` |

## Deployment

Hosted on Render with a Supabase PostgreSQL database; both belong to the project owner.

- Build command: `pip install -r requirements.txt && flask db upgrade`
- Start command: `gunicorn wsgi:app`

After the first deploy, run `load-zones` and `create-admin` once against the Supabase database.

## Data sources

Bogotá localities (SDP), UPZ and public-space indicator (DADEP), cadastral sectors (UAECD),
waste critical points (UAESP) and locality population projections (SDP), all from
[Datos Abiertos Bogotá](https://datosabiertos.bogota.gov.co).
