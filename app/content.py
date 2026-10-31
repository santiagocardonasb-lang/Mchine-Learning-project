"""Text content for the About and How it works pages."""

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

HOW_IT_WORKS_INTRO = (
    "LocWaste turns citizen reports into a monthly forecast of where solid waste is "
    "likely to accumulate in Bogotá, so collection and prevention can reach those "
    "zones first."
)

# icon and color are Bootstrap Icons names and risk tokens used by the template.
HOW_IT_WORKS_STEPS = [
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

SYNTHETIC_NOTE = (
    "Until enough citizen reports exist, the model also learns from a 24-month synthetic "
    "history calibrated on these open datasets. Synthetic reports are labeled as such "
    "in the database."
)
