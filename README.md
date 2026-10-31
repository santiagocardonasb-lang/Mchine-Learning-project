# LocWaste

Flask web app where citizens report waste accumulation points in Bogotá. A machine learning
model predicts waste-accumulation risk per zone and shows it on a map.

## Run locally

```
python -m venv .venv
.venv\Scripts\activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env; then fill in SECRET_KEY (and DATABASE_URL for Postgres)
flask --app wsgi run
```

Without `DATABASE_URL` the app uses a local SQLite file in `instance/`.

Run the tests with `pytest`.
