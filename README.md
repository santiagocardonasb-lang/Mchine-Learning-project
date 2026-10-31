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
