def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


def test_readiness_endpoint(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.get_json()["database"] == "connected"


def test_version_and_instance_endpoints(client):
    assert client.get("/version").status_code == 200
    assert client.get("/instance").status_code == 200
