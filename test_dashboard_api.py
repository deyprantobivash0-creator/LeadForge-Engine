import requests


BASE_URL = "http://127.0.0.1:8000"


def get(url, expected_status=200):

    response = requests.get(url)

    print(f"\nGET {url}")
    print("Status:", response.status_code)

    assert response.status_code == expected_status

    if response.status_code == 200:
        print("Response:", response.json())

    return response


# Basic dashboard
get(
    f"{BASE_URL}/api/dashboard/overview"
)


# Limit
response = get(
    f"{BASE_URL}/api/dashboard/overview?limit=3"
)

data = response.json()

assert len(data["top_opportunities"]) <= 3
assert len(data["recent_analyses"]) <= 3


# Priority
response = get(
    f"{BASE_URL}/api/dashboard/overview?priority=Hot"
)

data = response.json()

for lead in data["top_opportunities"]:
    assert lead["priority"] == "Hot"

for lead in data["recent_analyses"]:
    assert lead["priority"] == "Hot"


# Priority + limit
response = get(
    f"{BASE_URL}/api/dashboard/overview?priority=Hot&limit=2"
)

data = response.json()

assert len(data["top_opportunities"]) <= 2
assert len(data["recent_analyses"]) <= 2


# Invalid limit
get(
    f"{BASE_URL}/api/dashboard/overview?limit=0",
    expected_status=422,
)


# Invalid priority
get(
    f"{BASE_URL}/api/dashboard/overview?priority=Invalid",
    expected_status=422,
)


print("\n========================================")
print("DASHBOARD API INTEGRATION TEST PASSED")
print("========================================")