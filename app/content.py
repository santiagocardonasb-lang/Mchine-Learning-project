"""Text content of the public project presentation at /."""

from ml import config

PROJECT_TITLE = (
    "Intelligent System for the Management and Prediction of Critical Urban "
    "Solid Waste Accumulation Zones Using Machine Learning"
)

PROBLEM_STATEMENT = [
    (
        "Urban solid waste generation is one of the main environmental challenges "
        "cities face. The World Bank estimates that 2.56 billion tonnes of municipal "
        "solid waste were generated in 2022, a figure that could reach 3.86 billion "
        "tonnes by 2050 without significant changes, and that about 30% of the "
        "world's municipal waste is dumped in the open or never collected "
        "(Cook et al., 2026)."
    ),
    (
        "In Colombia, 12,149,386 tonnes of solid waste were taken to final disposal "
        "sites in 2024 (SSPD, 2025). That report focuses on final disposal, so "
        "identifying where waste accumulates in public spaces, and how often it "
        "happens in each sector, requires local records."
    ),
    (
        "The problem this project addresses is the lack of an integrated tool that "
        "centralizes waste accumulation reports, allows their history to be "
        "consulted, displays the affected zones and uses the available data to "
        "estimate the risk of new accumulations."
    ),
]

SOLUTION_INTRO = (
    "LocWaste turns citizen reports into a monthly forecast of where solid waste is "
    "likely to accumulate in Bogotá, so collection and prevention can reach those "
    "zones first."
)

# icon and color are Bootstrap Icons names and risk tokens used by the template.
SOLUTION_STEPS = [
    {
        "icon": "geo-alt",
        "color": "brand",
        "title": "1. Report",
        "text": (
            "A registered citizen drops a pin where waste is piling up and describes "
            "it: type of waste, size, and whether there are rodents, insects, a strong "
            "odor or a river nearby. The locality, UPZ and neighborhood are detected "
            "from the pin."
        ),
    },
    {
        "icon": "fire",
        "color": "medium",
        "title": "2. See the hotspots",
        "text": (
            "Every report joins a heat map of the city. Reports are grouped by "
            "locality and UPZ (urban planning zone), so anyone can look at the whole "
            "city or focus on one area."
        ),
    },
    {
        "icon": "graph-up-arrow",
        "color": "high",
        "title": "3. Anticipate the risk",
        "text": (
            "Each month a Machine Learning classifier looks at the recent history of "
            "every UPZ (report counts and trends, share of large reports and of "
            "reports with vectors, real critical points, public space and population "
            "density) and predicts low, medium or high risk for the next month."
        ),
    },
]

DEFINITION = (
    "LocWaste is a web information system with a supervised classification model. The unit of "
    "analysis is one UPZ in one month; for each of Bogotá's 112 urban UPZ the model predicts "
    "whether next month's rate of accumulation reports will be low, medium or high."
)

RESEARCH_QUESTION = (
    "To what extent can an information system that integrates georeferenced "
    "reports and collection history, together with a Machine Learning "
    "classification model, identify and prioritize the zones with the highest "
    "risk of urban solid waste accumulation?"
)

GENERAL_OBJECTIVE = (
    "Develop an intelligent system for managing urban solid waste information "
    "using Machine Learning techniques, which centralizes reports, analyzes "
    "historical patterns, identifies critical zones and predicts the risk of "
    "waste accumulation to support decision-making."
)

SPECIFIC_OBJECTIVES = [
    "Centralize georeferenced citizen reports of waste accumulation, each placed in its "
    "locality, UPZ and neighborhood.",
    "Show the reports and the affected zones on a map of Bogotá, for the whole city or one area.",
    "Build a monthly dataset per UPZ from the reports and real open data, without leakage "
    "between predictors and target.",
    "Train and compare classifiers against a baseline with temporal cross-validation and "
    "serve the best one.",
    "Keep the model current by retraining it from the app as new reports arrive.",
]

DATA_SOURCES = [
    {
        "name": "Critical points of clandestine dumping",
        "publisher": "UAESP",
        "text": (
            "The real active critical points published by Bogotá's public services "
            "unit. They calibrate the initial synthetic history and are a feature of "
            "the model."
        ),
    },
    {
        "name": "Population by locality",
        "publisher": "SDP",
        "text": (
            "Population projections from the District Planning Secretariat, used to "
            "measure reports per inhabitant and population density."
        ),
    },
    {
        "name": "Bogotá boundaries",
        "publisher": "SDP · DADEP · UAECD",
        "text": (
            "Locality, UPZ and cadastral sector boundaries from Bogotá's open data "
            "portal. They place each report in its zone and draw the map."
        ),
    },
]

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

# Each phase is one tab; "bullets" adds a bullet list under a step.
PHASES = [
    {
        "slug": "understanding",
        "name": "Business and data understanding",
        "icon": "search",
        "summary": "What has to be predicted, why it matters and which data can answer it.",
        "steps": [
            {
                "title": "The problem",
                "text": (
                    "Waste piles up in public space before anyone records it. Collection and "
                    "awareness campaigns need to know where to go first."
                ),
            },
            {
                "title": "The target question",
                "text": (
                    "Which UPZ will have a high rate of accumulation reports next month? Success "
                    "means catching most high-risk zones (recall of the high class) without "
                    "flagging the whole city."
                ),
            },
            {
                "title": "The sources",
                "text": (
                    "Real open data from Bogotá describes each zone; citizen reports add date, "
                    "place, type, size, vectors and nearby water."
                ),
                "bullets": [f"{s['publisher']} — {s['name']}: {s['text']}" for s in DATA_SOURCES],
            },
        ],
    },
    {
        "slug": "preparation",
        "name": "Data preparation",
        "icon": "table",
        "summary": "From boundaries and reports to one clean row per UPZ and month.",
        "steps": [
            {
                "title": "Zones",
                "text": (
                    "Boundaries of 19 urban localities and 112 UPZ, cadastral sectors as "
                    "neighborhoods, 478 active UAESP critical points, the DADEP public space "
                    "indicator and SDP population. Every report is placed in its zone from the pin."
                ),
            },
            {
                "title": "Synthetic history",
                "text": (
                    "The model needs history from day one, so the first months are synthetic, "
                    "calibrated on the real open data and stored with source = synthetic. "
                    "Its assumptions:"
                ),
                "bullets": SYNTHETIC_ASSUMPTIONS + [POPULATION_SOURCE],
            },
            {
                "title": "UPZ × month table",
                "text": (
                    "Reports are grouped into one row per UPZ and month: the month's count and rate "
                    "per 10,000 inhabitants, lags of 1 to 3 months, a 3-month average, the "
                    "month-over-month change, shares of large piles, vectors and water, reports "
                    "still open at month end, the month of the year and the zone's fixed "
                    "attributes. Rejected reports are left out."
                ),
            },
            {
                "title": "Next-month target without leakage",
                "text": (
                    "The target is the risk level of month t+1: next month's reports per 10,000 "
                    "inhabitants split into terciles (low, medium, high), with the cut points "
                    "computed on the training months only. Features use data up to the end of "
                    "month t, so the target never comes from the predictors' own period."
                ),
            },
        ],
    },
    {
        "slug": "modeling",
        "name": "Modeling and evaluation",
        "icon": "diagram-3",
        "summary": "Three classifiers, compared over time, and a clear rule to choose one.",
        "steps": [
            {
                "title": "Baseline",
                "text": (
                    "A most-frequent classifier sets the floor any useful model has to beat."
                ),
            },
            {
                "title": "Logistic regression and random forest",
                "text": (
                    "Both predict next month's level with balanced class weights, so the high "
                    "class is not drowned out by the others."
                ),
            },
            {
                "title": "Temporal cross-validation",
                "text": (
                    f"The last {config.TEST_MONTHS_FRACTION:.0%} of the months are held out as the "
                    f"test set. On the earlier months, a {config.N_SPLITS}-fold TimeSeriesSplit "
                    "gives mean ± std per model, always training on the past and validating on "
                    "the future."
                ),
            },
            {
                "title": "Why one model is chosen",
                "text": (
                    "The model with the best cross-validated macro-F1, then recall of the high "
                    "class, is served. Accuracy is shown but not used to choose, because a model "
                    "can score well on it while missing the high-risk zones."
                ),
            },
        ],
    },
    {
        "slug": "deployment",
        "name": "Deployment",
        "icon": "rocket-takeoff",
        "summary": "The model runs inside the app citizens and admins use every day.",
        "steps": [
            {
                "title": "The app",
                "text": (
                    "A Flask app on Render stores every training run in the database, with its "
                    "parameters, metrics and the trained model."
                ),
            },
            {
                "title": "Citizen reports",
                "text": (
                    "Registered users report waste points on a map; admins moderate them, and "
                    "rejected reports never reach the model."
                ),
            },
            {
                "title": "Risk map",
                "text": (
                    "The map shows the reports of the chosen period as a heat map and the active "
                    "run's next-month risk for every UPZ."
                ),
            },
            {
                "title": "Automatic retraining",
                "text": (
                    "Admins can retrain from the app, and training starts by itself after "
                    f"{config.AUTO_RETRAIN_THRESHOLD} new citizen reports."
                ),
            },
        ],
    },
]
