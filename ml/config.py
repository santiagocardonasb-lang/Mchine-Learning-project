"""Every parameter of the synthetic data and the model. The model page renders these values."""

RANDOM_STATE = 42

# Synthetic history (spec section 8)
SYNTHETIC_START = "2024-11-01"
SYNTHETIC_MONTHS = 24
SYNTHETIC_MONTHLY_REPORTS = 630  # ~750 a month once seasonality and noise are applied
RAINY_MONTHS = (4, 5, 10, 11)
RAINY_SEASON_FACTOR = 1.25
PERSISTENCE = 0.6  # autocorrelation of each UPZ's monthly level
NOISE_SD = 0.35
NEAR_CRITICAL_POINT_SHARE = 0.6

# Target
RISK_LEVELS = ("low", "medium", "high")
RATE_PER_INHABITANTS = 10_000

# Validation
TEST_MONTHS_FRACTION = 0.20
N_SPLITS = 5
MIN_MONTHS = 12

# Models
CLASS_WEIGHT = "balanced"
LOGREG_C = 1.0
LOGREG_MAX_ITER = 2000
N_ESTIMATORS = 300
MAX_DEPTH = 8
MIN_SAMPLES_LEAF = 5

# Retraining
AUTO_RETRAIN_THRESHOLD = 50

FEATURES = [
    "reports",
    "rate",
    "lag_1",
    "lag_2",
    "lag_3",
    "rolling_mean_3",
    "change_1",
    "share_large",
    "share_vectors",
    "share_near_water",
    "open_at_month_end",
    "month_of_year",
    "critical_points",
    "public_space_m2_per_inhabitant",
    "population_density",
]

FEATURE_LABELS = {
    "reports": "Reports this month",
    "rate": "Reports per 10,000 inhabitants",
    "lag_1": "Reports last month",
    "lag_2": "Reports 2 months ago",
    "lag_3": "Reports 3 months ago",
    "rolling_mean_3": "3-month average",
    "change_1": "Change vs last month",
    "share_large": "Share of large piles",
    "share_vectors": "Share with vectors",
    "share_near_water": "Share near water",
    "open_at_month_end": "Open at month end",
    "month_of_year": "Month of year",
    "critical_points": "Real critical points",
    "public_space_m2_per_inhabitant": "Public space per inhabitant",
    "population_density": "Population density",
}


def as_dict() -> dict:
    """The values stored in model_runs.params for each run."""
    return {
        name: value
        for name, value in globals().items()
        if name.isupper() and name not in ("FEATURES", "FEATURE_LABELS")
    }