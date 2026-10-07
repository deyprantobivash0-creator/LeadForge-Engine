import requests


BASE_URL = "http://127.0.0.1:8000"


def request(
    method: str,
    url: str,
    expected_status: int,
    payload: dict | None = None,
):
    response = requests.request(
        method,
        url,
        json=payload,
    )

    print(f"\n{method} {url}")
    print("Status:", response.status_code)

    assert response.status_code == expected_status

    if response.content:
        data = response.json()
        print("Response:", data)
        return data

    return None


# -----------------------------------------
# Find an existing lead
# -----------------------------------------

leads = request(
    "GET",
    f"{BASE_URL}/api/leads/",
    200,
)

assert isinstance(leads, list)
assert len(leads) > 0

lead_id = leads[0]["id"]

print("\nTesting Lead ID:", lead_id)


# -----------------------------------------
# Update lifecycle
# -----------------------------------------

updated = request(
    "PATCH",
    f"{BASE_URL}/api/leads/{lead_id}/lifecycle",
    200,
    {
        "status": "Contacted",
        "notes": "Lifecycle integration test.",
        "last_contacted": "2026-08-27T10:00:00",
        "next_follow_up": "2026-08-28T10:00:00",
    },
)

assert updated["status"] == "Contacted"
assert updated["notes"] == "Lifecycle integration test."


# -----------------------------------------
# Verify lead detail
# -----------------------------------------

detail = request(
    "GET",
    f"{BASE_URL}/api/leads/{lead_id}",
    200,
)

assert detail["id"] == lead_id


# -----------------------------------------
# Verify follow-up endpoint
# -----------------------------------------

follow_ups = request(
    "GET",
    f"{BASE_URL}/api/leads/follow-ups?days=3",
    200,
)

assert isinstance(follow_ups, list)

matching_lead = [
    lead
    for lead in follow_ups
    if lead["id"] == lead_id
]

assert len(matching_lead) == 1


# -----------------------------------------
# Invalid status
# -----------------------------------------

request(
    "PATCH",
    f"{BASE_URL}/api/leads/{lead_id}/lifecycle",
    422,
    {
        "status": "InvalidStatus",
    },
)


# -----------------------------------------
# Invalid follow-up range
# -----------------------------------------

request(
    "GET",
    f"{BASE_URL}/api/leads/follow-ups?days=31",
    422,
)


print("\n========================================")
print("LEAD LIFECYCLE INTEGRATION TEST PASSED")
print("========================================")