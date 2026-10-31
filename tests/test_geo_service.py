from app.services import geo_service


def test_locate_plaza_de_bolivar():
    match = geo_service.locate(4.5981, -74.0760)
    assert match is not None
    assert "candelaria" in match.locality_name.lower()
    assert match.upz_name


def test_locate_kennedy():
    match = geo_service.locate(4.6280, -74.1630)
    assert match is not None
    assert "kennedy" in match.locality_name.lower()


def test_locate_outside_returns_none():
    assert geo_service.locate(4.0, -74.0) is None


def test_search_neighborhoods_matches_substring_ignoring_case():
    results = geo_service.search_neighborhoods("tintal")
    assert results
    assert all("tintal" in r["name"].lower() for r in results)
    assert set(results[0]) == {"name", "lat", "lon"}


def test_search_neighborhoods_ignores_accents():
    assert geo_service.search_neighborhoods("usaquen") == geo_service.search_neighborhoods("USAQUÉN")


def test_search_neighborhoods_short_query_is_empty():
    assert geo_service.search_neighborhoods("") == []
    assert geo_service.search_neighborhoods("a") == []


def test_search_neighborhoods_respects_limit_and_prefix_first():
    results = geo_service.search_neighborhoods("san", limit=5)
    assert len(results) == 5
    assert results[0]["name"].lower().startswith("san")
