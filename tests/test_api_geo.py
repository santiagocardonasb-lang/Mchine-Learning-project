def test_localities_endpoint_returns_feature_collection(client):
    response = client.get("/api/geo/localities")
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    data = response.get_json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 19


def test_upz_endpoint_returns_feature_collection(client):
    response = client.get("/api/geo/upz")
    assert response.status_code == 200
    assert len(response.get_json()["features"]) == 112


def test_locate_inside(client):
    response = client.get("/api/geo/locate?lat=4.5981&lon=-74.0760")
    assert response.status_code == 200
    data = response.get_json()
    assert "candelaria" in data["locality_name"].lower()
    assert set(data) == {"locality_code", "locality_name", "upz_code", "upz_name", "neighborhood"}


def test_locate_outside_is_404(client):
    response = client.get("/api/geo/locate?lat=4.0&lon=-74.0")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Outside the covered area"}


def test_locate_non_numeric_is_400(client):
    response = client.get("/api/geo/locate?lat=abc&lon=-74.0")
    assert response.status_code == 400
    assert response.get_json() == {"error": "lat and lon must be numbers"}


def test_locate_missing_params_is_400(client):
    assert client.get("/api/geo/locate").status_code == 400


def test_neighborhoods_search(client):
    response = client.get("/api/neighborhoods?q=tintal")
    assert response.status_code == 200
    data = response.get_json()
    assert data and all("tintal" in item["name"].lower() for item in data)


def test_neighborhoods_without_query_is_empty_list(client):
    assert client.get("/api/neighborhoods").get_json() == []
