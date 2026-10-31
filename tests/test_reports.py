import pytest

from app.forms.report import SIZE_CHOICES, WASTE_TYPE_CHOICES
from app.extensions import db
from app.models import SIZES, WASTE_TYPES, Report, User
from app.services import auth_service, report_service
from app.services.report_service import OutsideCoverage

KENNEDY = {"latitude": "4.6280", "longitude": "-74.1630"}


@pytest.fixture
def zones(app, db_session):
    result = app.test_cli_runner().invoke(args=["load-zones"])
    assert result.exit_code == 0, result.output


@pytest.fixture
def user(db_session):
    return auth_service.register("Ana", "ana@mail.com", "secret123")


@pytest.fixture
def logged_in(client, user):
    client.post("/auth/login", data={"email": "ana@mail.com", "password": "secret123"})
    return client


def report_form(**overrides):
    return {**KENNEDY, "waste_type": "household", "size": "medium", "has_rodents": "y", **overrides}


def test_report_in_kennedy_is_created_and_redirects_to_map(logged_in, zones, user):
    response = logged_in.post("/reports/new", data=report_form())

    assert response.status_code == 302
    assert response.headers["Location"] == "/map"
    report = Report.query.one()
    assert report.upz_id is not None
    assert report.locality.name.lower() == "kennedy"
    assert report.source == "user"
    assert report.status == "open"
    assert report.user_id == user.id
    assert report.has_rodents and not report.has_insects

    html = logged_in.get(response.headers["Location"]).get_data(as_text=True)
    assert "Report sent" in html


def test_report_outside_coverage_is_not_created(logged_in, zones):
    response = logged_in.post("/reports/new", data=report_form(latitude="4.0", longitude="-74.0"))

    assert response.status_code == 200
    assert "outside the covered area" in response.get_data(as_text=True).lower()
    assert Report.query.count() == 0


def test_report_without_loaded_zones_is_not_created(logged_in):
    response = logged_in.post("/reports/new", data=report_form())

    assert response.status_code == 200
    assert "Reports are temporarily unavailable. Please try again later." in response.get_data(as_text=True)
    assert Report.query.count() == 0


def test_failing_hook_does_not_break_a_saved_report(logged_in, zones, monkeypatch):
    def broken_hook(report):
        raise RuntimeError("retrain failed")

    monkeypatch.setattr(report_service, "on_created", [broken_hook])

    response = logged_in.post("/reports/new", data=report_form())

    assert response.status_code == 302
    assert response.headers["Location"] == "/map"
    assert Report.query.count() == 1
    assert "Report sent" in logged_in.get("/map").get_data(as_text=True)

def test_hook_with_failed_flush_does_not_break_a_saved_report(logged_in, zones, monkeypatch):
    def duplicate_email_hook(report):
        db.session.add(User(name="Dup", email="ana@mail.com", password_hash="x"))
        db.session.flush()

    monkeypatch.setattr(report_service, "on_created", [duplicate_email_hook])

    response = logged_in.post("/reports/new", data=report_form())

    assert response.status_code == 302
    assert response.headers["Location"] == "/map"
    assert Report.query.count() == 1
    assert "Report sent" in logged_in.get("/map").get_data(as_text=True)


def test_report_with_invalid_waste_type_is_rejected(logged_in, zones):
    response = logged_in.post("/reports/new", data=report_form(waste_type="nuclear"))

    assert response.status_code == 200
    assert Report.query.count() == 0


def test_report_note_longer_than_500_chars_is_rejected(logged_in, zones):
    response = logged_in.post("/reports/new", data=report_form(description="x" * 501))

    assert response.status_code == 200
    assert Report.query.count() == 0


def test_form_choices_match_model_enums():
    assert [c.value for c in WASTE_TYPE_CHOICES] == list(WASTE_TYPES)
    assert [c.value for c in SIZE_CHOICES] == list(SIZES)


def test_guest_is_redirected_to_login(client, db_session):
    response = client.get("/reports/new")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")


def test_report_page_presets_pin_from_query(logged_in):
    html = logged_in.get("/reports/new?lat=4.62&lon=-74.15").get_data(as_text=True)

    assert 'value="4.62"' in html
    assert 'value="-74.15"' in html


def test_create_raises_outside_coverage(zones, user):
    with pytest.raises(OutsideCoverage):
        report_service.create(user, 4.0, -74.0, "household", "small",
                              False, False, False, False, None)
    assert Report.query.count() == 0


def test_create_runs_on_created_hooks(zones, user, monkeypatch):
    seen = []
    monkeypatch.setattr(report_service, "on_created", [seen.append])

    report = report_service.create(user, 4.6280, -74.1630, "bulky", "large",
                                   False, True, True, False, "Behind the park")

    assert seen == [report]
    assert report.id is not None


def test_public_dict_has_no_user_fields(zones, user):
    report = report_service.create(user, 4.6280, -74.1630, "organic", "small",
                                   False, False, False, True, None)

    data = report_service.public_dict(report)

    assert set(data) == {"id", "latitude", "longitude", "locality", "upz", "neighborhood",
                         "reported_at", "waste_type", "size", "status"}
    assert not {"user_id", "name", "email"} & set(data)
    assert data["locality"].lower() == "kennedy"
    assert data["reported_at"].startswith(str(report.reported_at.year))


def test_map_is_public(client, db_session):
    response = client.get("/map")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Bogotá at a glance" in html
    assert "Predictions appear after the first model run" in html


def test_expired_csrf_on_report_form_redirects_with_flash(app, user):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    response = client.post("/reports/new", data=report_form(), headers={"Referer": "http://localhost/reports/new"})

    assert response.status_code == 302
    assert response.headers["Location"] == "http://localhost/reports/new"
    assert Report.query.count() == 0
    with client.session_transaction() as sess:
        assert ("error", "Your session expired. Please try again.") in sess["_flashes"]
