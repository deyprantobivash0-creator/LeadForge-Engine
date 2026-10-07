import requests


BASE_URL = "http://127.0.0.1:8000"


def get(url, expected_status=200):
    response = requests.get(url)

    print(f"\nGET {url}")
    print("Status:", response.status_code)

    assert response.status_code == expected_status

    if response.status_code == 200:
        data = response.json()
        print("Response:", data)
        return data

    return None


# -----------------------------------------
# List leads
# -----------------------------------------

leads_response = get(
    f"{BASE_URL}/api/leads/"
)

assert isinstance(leads_response, list)


# -----------------------------------------
# Get a specific lead
# -----------------------------------------

if leads_response:

    lead_id = leads_response[0]["id"]

    detail = get(
        f"{BASE_URL}/api/leads/{lead_id}"
    )

    assert detail["id"] == lead_id
    assert "company" in detail
    assert "email" in detail
    assert "source" in detail
    assert "analysis" in detail


# -----------------------------------------
# Search by company
# -----------------------------------------

search_company = get(
    f"{BASE_URL}/api/leads/search?company=tesla"
)

assert isinstance(search_company, list)

for lead in search_company:
    assert "tesla" in lead["company"].lower()


# -----------------------------------------
# Search by email
# -----------------------------------------

search_email = get(
    f"{BASE_URL}/api/leads/search?email=tesla"
)

assert isinstance(search_email, list)

for lead in search_email:
    assert "tesla" in lead["email"].lower()


# -----------------------------------------
# Combined search
# -----------------------------------------

combined = get(
    f"{BASE_URL}/api/leads/search"
    f"?company=tesla&email=sales"
)

assert isinstance(combined, list)

for lead in combined:

    assert "tesla" in lead["company"].lower()
    assert "sales" in lead["email"].lower()


# -----------------------------------------
# Non-existent lead
# -----------------------------------------

get(
    f"{BASE_URL}/api/leads/999999",
    expected_status=200,
)


print("\n========================================")
print("LEAD MANAGEMENT API TEST PASSED")
print("========================================")