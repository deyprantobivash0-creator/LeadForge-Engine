def test_get_leads(client):
    response = client.get(
        "/api/leads/?page=1&page_size=50"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 50

    def test_invalid_page(client:any):
        response = client.get(
        "/api/leads/?page=0"
    )

    assert response.status_code == 422


def test_invalid_page_size(client):
    response = client.get(
        "/api/leads/?page_size=101"
    )

    assert response.status_code == 422