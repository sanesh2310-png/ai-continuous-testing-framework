import pytest

pytestmark = pytest.mark.api
VALID = {"email": "tester@shop.com", "password": "Test@123"}


@pytest.mark.case("API-001", "API Health Endpoint", expected="HTTP 200 and status ok",
                  category="API", severity="Low")
@pytest.mark.smoke
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200, f"Expected HTTP 200 but got {r.status_code}"
    assert r.get_json() == {"status": "ok"}


@pytest.mark.case("API-002", "API Product Endpoint", expected="HTTP 200 and 8 products",
                  category="API", severity="High")
def test_product_list(client):
    r = client.get("/api/products")
    assert r.status_code == 200, f"Expected HTTP 200 but got {r.status_code}"
    assert len(r.get_json()) == 8, f"Expected 8 products but got {len(r.get_json())}"


@pytest.mark.case("API-003", "API Product Search", expected="Only products matching 'laptop'",
                  category="Search", severity="Medium")
def test_product_search(client):
    names = [p["name"] for p in client.get("/api/products?q=laptop").get_json()]
    assert names and all("laptop" in n.lower() for n in names), f"Unexpected search results: {names}"


@pytest.mark.case("API-004", "API Search With No Match", expected="HTTP 200 and empty list",
                  category="Search", severity="Low")
def test_product_search_no_match(client):
    r = client.get("/api/products?q=zzzz")
    assert r.status_code == 200 and r.get_json() == [], f"Expected empty list but got {r.get_json()}"


@pytest.mark.case("API-005", "API Unknown Product", expected="HTTP 404",
                  category="API", severity="Low")
def test_unknown_product(client):
    r = client.get("/api/products/999")
    assert r.status_code == 404, f"Expected HTTP 404 but got {r.status_code}"


@pytest.mark.case("API-006", "API Valid Login", expected="HTTP 200 and a token",
                  category="Authentication", severity="Critical")
@pytest.mark.smoke
def test_login_valid(client):
    r = client.post("/api/login", json=VALID)
    assert r.status_code == 200, f"Expected HTTP 200 but got {r.status_code}"
    assert r.get_json().get("token"), "Expected a token in the response"


@pytest.mark.case("API-007", "API Invalid Login Validation (wrong password)",
                  expected="HTTP 401 for a wrong password",
                  category="Authentication", severity="Critical")
def test_login_wrong_password(client):
    r = client.post("/api/login", json={**VALID, "password": "WrongPass1"})
    assert r.status_code == 401, f"Expected HTTP 401 but got {r.status_code} (wrong password was accepted)"


@pytest.mark.case("API-008", "API Login Input Validation", expected="HTTP 400 with a validation message",
                  category="Input Validation", severity="Medium")
@pytest.mark.parametrize("payload", [
    {"email": "not-an-email", "password": "Test@123"},
    {"email": "tester@shop.com", "password": "123"},
    {"email": "", "password": ""},
    {},
], ids=["bad-email", "short-password", "empty-fields", "no-body"])
def test_login_validation(client, payload):
    r = client.post("/api/login", json=payload)
    assert r.status_code == 400, f"Expected HTTP 400 but got {r.status_code}"
