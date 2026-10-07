def test_get_leads(tenant_workspace):
    response = tenant_workspace["clients"]["a"].get(
        "/api/leads/?page=1&page_size=50",
        headers={"X-Organization-ID": str(tenant_workspace["ids"]["organizations"]["a"])},
    )

    assert response.status_code == 200

    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 50

def test_invalid_page(tenant_workspace):
    response = tenant_workspace["clients"]["a"].get(
        "/api/leads/?page=0",
        headers={"X-Organization-ID": str(tenant_workspace["ids"]["organizations"]["a"])},
    )

    assert response.status_code == 422


def test_invalid_page_size(tenant_workspace):
    response = tenant_workspace["clients"]["a"].get(
        "/api/leads/?page_size=101",
        headers={"X-Organization-ID": str(tenant_workspace["ids"]["organizations"]["a"])},
    )

    assert response.status_code == 422
