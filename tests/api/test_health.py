def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["status"] == "healthy"


def test_ready_endpoint(client):
    response = client.get("/ready")

    assert response.status_code in {200, 503}

    data = response.json()

    assert "status" in data

def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True    