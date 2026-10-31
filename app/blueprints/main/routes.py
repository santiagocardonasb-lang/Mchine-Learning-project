from app.blueprints.main import main_bp


@main_bp.route("/")
def home():
    return "LocWaste"
