"""Text content of the public project presentation at /."""

from datetime import date, timedelta

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
                "title": "The target question and success criteria",
                "text": (
                    "Which UPZ will have a high rate of accumulation reports next month? Success "
                    "means catching most high-risk zones (recall of the high class) without "
                    "flagging the whole city, measured with macro-F1 against a baseline."
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
            {
                "title": "Quality assurance",
                "text": (
                    "The data needed was checked against what is published: UPZ population and "
                    "river data do not exist as open data, so both are documented as assumptions."
                ),
            },
        ],
    },
    {
        "slug": "data",
        "name": "Data engineering",
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
                    "Reports are grouped into one row per UPZ and complete calendar month: the "
                    "month's count and rate per 10,000 inhabitants, lags of 1 to 3 months, a "
                    "3-month average, the month-over-month change, shares of large piles, vectors "
                    "and water, reports still open at month end, the month of the year and the "
                    "zone's fixed attributes. Rejected reports are left out."
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
        "name": "Model engineering",
        "icon": "diagram-3",
        "summary": "Three classifiers with fixed, visible parameters and a version for every run.",
        "steps": [
            {
                "title": "Baseline",
                "text": "A most-frequent classifier sets the floor any useful model has to beat.",
            },
            {
                "title": "Logistic regression and random forest",
                "text": (
                    f"Logistic regression (C = {config.LOGREG_C}) and a random forest of "
                    f"{config.N_ESTIMATORS} trees with maximum depth {config.MAX_DEPTH} and at least "
                    f"{config.MIN_SAMPLES_LEAF} samples per leaf. Both use balanced class weights, "
                    "so the high class is not drowned out by the others."
                ),
            },
            {
                "title": "Reproducible runs",
                "text": (
                    f"All parameters live in ml/config.py with a fixed seed ({config.RANDOM_STATE}). "
                    "Each training run is stored as a new model version with its parameters, "
                    "metrics and the trained model."
                ),
            },
        ],
    },
    {
        "slug": "evaluation",
        "name": "Model evaluation",
        "icon": "clipboard-data",
        "summary": "Compared over time against the baseline, with a clear rule to choose one.",
        "steps": [
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
            {
                "title": "Error analysis",
                "text": (
                    "The confusion matrix and feature importances of every run are shown in the "
                    "app. Most errors fall between neighboring levels (medium and high), very few "
                    "between low and high."
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
                    "A Flask app on Render with PostgreSQL on Supabase. The ml package has no Flask "
                    "code, so training and the app compute exactly the same features."
                ),
            },
            {
                "title": "Roles",
                "text": (
                    "Citizens report waste points, see the map and check a zone's risk; admins "
                    "moderate reports, manage users, retrain and manage collection priorities. "
                    "Rejected reports never reach the model."
                ),
            },
            {
                "title": "Batch and on-demand inference",
                "text": (
                    "Every training run predicts next month's level for all UPZ, shown on the risk "
                    "map; the high-risk ones become pending collection tasks. Any signed-in user "
                    "can run a risk check for one UPZ and get the level and class probabilities."
                ),
            },
        ],
    },
    {
        "slug": "monitoring",
        "name": "Monitoring and maintenance",
        "icon": "activity",
        "summary": "Watching the app and the model, and retraining when they drift.",
        "steps": [
            {
                "title": "Logs",
                "text": (
                    "Every request, error and prediction is stored, with its user, model version, "
                    "result and duration."
                ),
            },
            {
                "title": "Outcomes, drift and performance",
                "text": (
                    "Each predicted month is compared with what happened. A drift check (PSI of the "
                    f"report rate above {config.DRIFT_PSI_THRESHOLD}, or a waste type, size or "
                    f"vector share moving more than {config.DRIFT_SHARE_THRESHOLD:.0%}) and a "
                    f"performance check (live macro-F1 below {config.PERFORMANCE_DROP_FRACTION:.0%} "
                    "of the cross-validation score) recommend retraining."
                ),
            },
            {
                "title": "Retraining",
                "text": (
                    "Admins retrain from the app, and training starts by itself after "
                    f"{config.AUTO_RETRAIN_THRESHOLD} new citizen reports."
                ),
            },
            {
                "title": "Feedback",
                "text": (
                    "Users report incidents, bugs and suggestions from any page; admins answer "
                    "them in the app."
                ),
            },
        ],
    },
]

REPOSITORY_URL = "https://github.com/santiagocardonasb-lang/Mchine-Learning-project"

# Studies, theory and concepts the project builds on; citations match REFERENCES.
RELATED_WORK = [
    {
        "title": "AI in solid waste management",
        "cite": "Abdallah et al., 2020",
        "text": (
            "A systematic review of 85 studies that apply artificial intelligence to waste "
            "forecasting, bin level detection, process parameters, collection routes and planning. "
            "Forecasting where and how much waste appears is one of its main application areas."
        ),
    },
    {
        "title": "Predicting waste at small scale",
        "cite": "Kontokosta et al., 2018",
        "text": (
            "Machine learning with small area estimation predicts building-level waste generation "
            "in New York City from collection records, building attributes and neighborhood "
            "characteristics, to support collection routes and policy."
        ),
    },
    {
        "title": "Finding likely dumping sites",
        "cite": "Geng et al., 2024",
        "text": (
            "A random forest ensemble trained on a few reported illegal dumping sites ranks the "
            "rest of the territory by risk; its top 30% of predicted areas covered 68.1% of the "
            "cases reported later. LocWaste applies the same idea to citizen reports and UPZ."
        ),
    },
]

THEORY = [
    (
        "Random forest",
        "An ensemble of decision trees, each trained on a bootstrap sample and a random subset of "
        "features, whose votes are combined. It captures non-linear relations and gives feature "
        "importances (Breiman, 2001).",
    ),
    (
        "Logistic regression and baseline",
        "A linear probabilistic classifier and a most-frequent classifier give a simple reference "
        "and a floor that any useful model has to beat (Pedregosa et al., 2011).",
    ),
    (
        "Time series validation",
        "With data ordered in time, models are trained on the past and validated on the future, so "
        "the estimate does not use information that would not exist at prediction time "
        "(Bergmeir & Benítez, 2012).",
    ),
    (
        "Synthetic data",
        "Data generated by a model of the real process. It fills the gap when real records do not "
        "exist yet, and is only trustworthy if its assumptions are explicit and it is kept apart "
        "from real data (Jordon et al., 2022; Patki et al., 2016).",
    ),
    (
        "Concept drift",
        "The relation between inputs and the target can change over time, so a deployed model has "
        "to be monitored and retrained (Gama et al., 2014; Sculley et al., 2015).",
    ),
]

CONCEPTS = [
    ("UPZ", "Urban planning zone (Unidad de Planeamiento Zonal); Bogotá has 112 urban UPZ in 19 localities."),
    ("Critical point", "A place where waste is dumped repeatedly, registered by UAESP."),
    ("Zone-month", "One UPZ in one calendar month: the unit of analysis and one row of the dataset."),
    ("Data leakage", "Using information from the target's period to build the predictors."),
    ("Macro-F1", "The average F1 of the three classes, so the high-risk class weighs as much as the others."),
    ("Recall of the high class", "Share of the zones that really were high risk that the model flagged."),
    ("PSI", "Population stability index: how much a feature's distribution moved; above 0.2 is a significant shift."),
    ("Inference", "Using the trained model to predict on new data, in batch for every UPZ or on demand for one."),
]

METHODOLOGY = [
    (
        "The project follows CRISP-ML(Q), the machine learning process model of Studer et al. "
        "(2021). It extends CRISP-DM with phases for model engineering, evaluation, deployment and "
        "monitoring, and attaches quality assurance to each phase: define requirements, check "
        "them and document the risks."
    ),
    (
        "The system was developed in parts, each on its own Git branch with small, ordered commits "
        "and merged through a pull request after review: the foundation (sign-in, zones, reports "
        "and map), data and model, results, the professor's feedback, operations and the final "
        "documentation. Every merge to master is deployed to Render, and the automated test suite "
        "runs before each one."
    ),
]

PLANNING_LEAD = timedelta(weeks=2)

# Actual dates come from the repository history; each activity was planned two weeks earlier.
SCHEDULE = [
    {
        "activity": "Project proposal and feedback",
        "responsible": "All members",
        "actual": date(2026, 10, 9),
        "deliverable": "Problem, objectives and scope reviewed by the professor",
    },
    {
        "activity": "Project approval",
        "responsible": "All members",
        "actual": date(2026, 10, 16),
        "deliverable": "Approved proposal",
    },
    {
        "activity": "First published version",
        "responsible": "Santiago Cardona",
        "actual": date(2026, 10, 23),
        "deliverable": "Homepage with title, problem and objective on Render",
    },
    {
        "activity": "Foundation: sign-in, zones, reports and map",
        "responsible": "Santiago Cardona",
        "actual": date(2026, 10, 31),
        "deliverable": "Roles, Bogotá zones, report form, map and database on Supabase",
    },
    {
        "activity": "Data and model",
        "responsible": "Jhon Correa",
        "actual": date(2026, 11, 2),
        "deliverable": "Synthetic history, UPZ-month features, trained and compared models",
    },
    {
        "activity": "Results: risk map, admin panel and my reports",
        "responsible": "Holman Herrera",
        "actual": date(2026, 11, 4),
        "deliverable": "Risk layers, heat map, zone detail, moderation and user management",
    },
    {
        "activity": "Integration review and fixes",
        "responsible": "Santiago Cardona",
        "actual": date(2026, 11, 6),
        "deliverable": "Leakage, artifact and retraining fixes merged to master",
    },
    {
        "activity": "Professor's feedback",
        "responsible": "Santiago Cardona",
        "actual": date(2026, 11, 7),
        "deliverable": "Public presentation, app behind sign-in, this-month period",
    },
    {
        "activity": "Operations (R3A3 Speaking Models)",
        "responsible": "Santiago Cardona",
        "actual": date(2026, 11, 15),
        "deliverable": "Risk check, inference log, priorities, monitoring, feedback and report",
    },
    {
        "activity": "Final documentation and presentation",
        "responsible": "All members",
        "actual": date(2026, 11, 16),
        "deliverable": "Complete homepage, consolidated technical report and 20-minute video",
    },
]
for item in SCHEDULE:
    item["planned"] = item["actual"] - PLANNING_LEAD

# url None means the resource is not published yet.
RESOURCES = [
    {
        "icon": "file-earmark-pdf",
        "title": "Technical report",
        "text": "The consolidated report of the three activities, in APA format.",
        "url": "/static/docs/LocWaste_Final_Report.pdf",
    },
    {
        "icon": "clipboard-check",
        "title": "CRISP-ML evidence",
        "text": "What was done in each phase, with the files, commits and results that prove it.",
        "url": f"{REPOSITORY_URL}/blob/master/docs/crisp-ml-evidence.md",
    },
    {
        "icon": "github",
        "title": "Repository",
        "text": "Source code, tests, migrations, data and commit history.",
        "url": REPOSITORY_URL,
    },
    {
        "icon": "book",
        "title": "User documentation",
        "text": "How citizens and administrators use every page of the app.",
        "url": f"{REPOSITORY_URL}/blob/master/docs/user-guide.md",
    },
    {
        "icon": "play-btn",
        "title": "Presentation video",
        "text": "The 20-minute presentation of the project and a live demo.",
        "url": None,
    },
]

# APA 7, in alphabetical order. Each entry is (text before the italics, italics, text after).
REFERENCES = [
    ("Abdallah, M., Abu Talib, M., Feroz, S., Nasir, Q., Abdalla, H., & Mahfood, B. (2020). "
     "Artificial intelligence applications in solid waste management: A systematic research review. ",
     "Waste Management, 109", ", 231–246. https://doi.org/10.1016/j.wasman.2020.04.057"),
    ("Bergmeir, C., & Benítez, J. M. (2012). On the use of cross-validation for time series "
     "predictor evaluation. ", "Information Sciences, 191", ", 192–213. https://doi.org/10.1016/j.ins.2011.12.028"),
    ("Breiman, L. (2001). Random forests. ", "Machine Learning, 45", "(1), 5–32. https://doi.org/10.1023/A:1010933404324"),
    ("Cook, E., Ionkova, K., Bhada-Tata, P., Yadav, S., & van Woerden, F. (2026). ",
     "What a waste 3.0: Global snapshot of solid waste management toward circularity until 2050",
     ". World Bank. https://www.worldbank.org/en/publication/what-a-waste"),
    ("Gama, J., Žliobaitė, I., Bifet, A., Pechenizkiy, M., & Bouchachia, A. (2014). A survey on "
     "concept drift adaptation. ", "ACM Computing Surveys, 46", "(4), Article 44. https://doi.org/10.1145/2523813"),
    ("Geng, J., Ding, Y., Xie, W., Fang, W., Liu, M., Ma, Z., Yang, J., & Bi, J. (2024). An ensemble "
     "machine learning model to uncover potential sites of hazardous waste illegal dumping based on "
     "limited supervision experience. ", "Fundamental Research, 4", "(4), 972–978. https://doi.org/10.1016/j.fmre.2023.06.010"),
    ("Jordon, J., Szpruch, L., Houssiau, F., Bottarelli, M., Cherubin, G., Maple, C., Cohen, S. N., & "
     "Weller, A. (2022). ", "Synthetic data — what, why and how?", " arXiv. https://doi.org/10.48550/arXiv.2205.03257"),
    ("Kontokosta, C. E., Hong, B., Johnson, N. E., & Starobin, D. (2018). Using machine learning and "
     "small area estimation to predict building-level municipal solid waste generation in cities. ",
     "Computers, Environment and Urban Systems, 70", ", 151–162. https://doi.org/10.1016/j.compenvurbsys.2018.03.004"),
    ("Patki, N., Wedge, R., & Veeramachaneni, K. (2016). The synthetic data vault. In ",
     "2016 IEEE International Conference on Data Science and Advanced Analytics (DSAA)",
     " (pp. 399–410). IEEE. https://doi.org/10.1109/DSAA.2016.49"),
    ("Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., "
     "Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., "
     "Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. ",
     "Journal of Machine Learning Research, 12", ", 2825–2830."),
    ("Sculley, D., Holt, G., Golovin, D., Davydov, E., Phillips, T., Ebner, D., Chaudhary, V., Young, M., "
     "Crespo, J.-F., & Dennison, D. (2015). Hidden technical debt in machine learning systems. In ",
     "Advances in Neural Information Processing Systems 28", " (pp. 2503–2511). Curran Associates."),
    ("Secretaría Distrital de Planeación. (2025). ",
     "Proyecciones y retroproyecciones de población por localidad 2005–2035",
     " [Data set]. Datos Abiertos Bogotá. https://datosabiertos.bogota.gov.co"),
    ("Studer, S., Bui, T. B., Drescher, C., Hanuschkin, A., Winkler, L., Peters, S., & Müller, K.-R. (2021). "
     "Towards CRISP-ML(Q): A machine learning process model with quality assurance methodology. ",
     "Machine Learning and Knowledge Extraction, 3", "(2), 392–413. https://doi.org/10.3390/make3020020"),
    ("Superintendencia de Servicios Públicos Domiciliarios. (2025). ",
     "Informe nacional de disposición final de residuos sólidos en Colombia en el año 2024",
     ". https://www.superservicios.gov.co"),
    ("Unidad Administrativa Especial de Servicios Públicos. (n.d.). ",
     "Puntos críticos de arrojo clandestino de residuos",
     " [Data set]. Datos Abiertos Bogotá. https://datosabiertos.bogota.gov.co"),
]
