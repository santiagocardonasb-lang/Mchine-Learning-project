"""The CRISP-ML evidence written by scripts/crisp_evidence.py, read once per process."""

import json
from functools import lru_cache
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent.parent / "static" / "crisp" / "evidence.json"

PHASES = [
    {"slug": "understanding", "name": "Business and data understanding", "icon": "search"},
    {"slug": "data", "name": "Data engineering", "icon": "table"},
    {"slug": "modeling", "name": "Model engineering", "icon": "diagram-3"},
    {"slug": "evaluation", "name": "Model evaluation", "icon": "clipboard-data"},
    {"slug": "deployment", "name": "Model deployment", "icon": "rocket-takeoff"},
    {"slug": "monitoring", "name": "Monitoring and maintenance", "icon": "activity"},
]


@lru_cache(maxsize=1)
def evidence() -> dict:
    return json.loads(EVIDENCE.read_text())


def phase(slug: str) -> dict | None:
    return next((p for p in PHASES if p["slug"] == slug), None)
