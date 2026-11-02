"""Text of the CRISP-DM page: the six phases applied to LocWaste."""

from ml import config

PHASES = [
    {
        "number": 1,
        "name": "Business understanding",
        "icon": "briefcase",
        "text": (
            "Waste piles up in public space before anyone records it. The goal is to anticipate "
            "which UPZ will have a high rate of accumulation reports next month, so collection "
            "and awareness campaigns can get there first. Success means catching most high-risk "
            "zones (recall of the high class) without flagging the whole city."
        ),
    },
    {
        "number": 2,
        "name": "Data understanding",
        "icon": "search",
        "text": (
            "Boundaries of 19 urban localities and 112 UPZ, cadastral sectors as neighborhoods, "
            "478 active UAESP clandestine-dumping critical points, the DADEP public space "
            "indicator and SDP population projections. Citizen reports add date, place, type, "
            "size, vectors and nearby water."
        ),
    },
    {
        "number": 3,
        "name": "Data preparation",
        "icon": "table",
        "text": (
            "Reports are grouped into one row per UPZ and month. Each row gets the month's count "
            "and rate per 10,000 inhabitants, lags of 1 to 3 months, a 3-month average, the "
            "month-over-month change, shares of large piles, vectors and water, reports still open "
            "at month end, the month of the year and the zone's fixed attributes. Rejected reports "
            "are left out."
        ),
    },
    {
        "number": 4,
        "name": "Modeling",
        "icon": "diagram-3",
        "text": (
            "Three classifiers predict next month's level: a most-frequent baseline, logistic "
            "regression and a random forest, both with balanced class weights. The model with "
            "the best cross-validated macro-F1 (then recall of the high class) is served."
        ),
    },
    {
        "number": 5,
        "name": "Evaluation",
        "icon": "clipboard-check",
        "text": (
            f"The last {config.TEST_MONTHS_FRACTION:.0%} of the months are held out as the test set. "
            f"On the earlier months, a {config.N_SPLITS}-fold TimeSeriesSplit gives mean ± std per "
            "model. Accuracy is shown but not used to choose, because a model can score well on "
            "it while missing the high-risk zones."
        ),
    },
    {
        "number": 6,
        "name": "Deployment",
        "icon": "rocket-takeoff",
        "text": (
            "The Flask app on Render stores every run in the database, with its parameters, "
            "metrics and the trained model. Admins can retrain from the app, and training starts "
            f"by itself after {config.AUTO_RETRAIN_THRESHOLD} new citizen reports. The map shows "
            "the active run's predictions."
        ),
    },
]

TARGET = (
    "Target: the risk level of month t+1. Next month's reports per 10,000 inhabitants are split "
    "into terciles (low, medium, high), with the cut points computed on the training months only. "
    "Features use data up to the end of month t, so the target never comes from the predictors' "
    "own period."
)

SYNTHETIC_ASSUMPTIONS = [
    f"{config.SYNTHETIC_MONTHS} months of history from {config.SYNTHETIC_START[:7]}, generated with "
    f"a fixed seed ({config.RANDOM_STATE}) by ml/synthetic.py; about 18,000 reports in total.",
    "A UPZ's expected monthly reports grow with its real UAESP critical points, its locality's "
    "population density and low public space per inhabitant. UPZ without critical points still "
    "get a small base.",
    f"Rainy months ({', '.join(str(m) for m in config.RAINY_MONTHS)}) multiply the expected count "
    f"by {config.RAINY_SEASON_FACTOR}.",
    f"Each UPZ's level persists from one month to the next (autocorrelation {config.PERSISTENCE}), "
    "which is what makes next month predictable.",
    f"{config.NEAR_CRITICAL_POINT_SHARE:.0%} of points are placed near a real critical point of "
    "their UPZ, the rest anywhere inside it. Construction debris is more frequent where critical "
    "points concentrate; rodents, insects and odor are more frequent with organic waste.",
    "River data is not part of the open data used, so each UPZ gets a fixed random chance of "
    "reports near water.",
    "UPZ population is not published; each locality's population is split among its UPZ by area.",
]

POPULATION_SOURCE = (
    "Population: SDP, projections and back-projections of population by locality 2005–2035 "
    "(March 2025 release), year 2026."
)