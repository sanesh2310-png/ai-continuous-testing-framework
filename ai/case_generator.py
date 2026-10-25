"""Generate test cases from a plain-English requirement / user story.

Uses an LLM when ANTHROPIC_API_KEY is set; otherwise a keyword-driven offline
generator (so it works without any key).

Each case is a dict:
  scenario, input, expected, kind ('positive'|'negative'|'boundary'),
  api_spec (dict or None)  -> lets the converter produce an executable PyTest script
"""
import json
import re

from ai.llm import ask

SYSTEM = """You are a senior QA engineer. Convert the requirement into 5-8 test cases.
Reply with ONLY a JSON array (no markdown). Each item has keys:
scenario, input, expected, kind (positive|negative|boundary), api_spec.
api_spec is null unless the case can be checked through the ShopEasy API:
  POST /api/login with json {"email","password"} -> 200 token | 400 validation | 401 bad credentials
  GET /api/products?q=<text> -> 200 JSON list
Valid credentials are tester@shop.com / Test@123; passwords need at least 6 characters.
When not null, api_spec is {"method":"POST"|"GET","path":"/api/...","json":{...} or null,
"status":<int>,"min_items":<int or omitted>,"max_items":<int or omitted>}."""

VALID = {"email": "tester@shop.com", "password": "Test@123"}


def _api(method, path, status, json_body=None, **extra):
    return {"method": method, "path": path, "json": json_body, "status": status, **extra}


def _login_cases():
    return [
        ("Valid login", "Correct email and password", "Login successful", "positive",
         _api("POST", "/api/login", 200, VALID)),
        ("Invalid password", "Correct email, wrong password", "Error message displayed (401)", "negative",
         _api("POST", "/api/login", 401, {**VALID, "password": "WrongPass1"})),
        ("Invalid email format", "Email 'not-an-email'", "Validation message displayed (400)", "negative",
         _api("POST", "/api/login", 400, {"email": "not-an-email", "password": "Test@123"})),
        ("Empty fields", "Email and password blank", "Required-field error (400)", "negative",
         _api("POST", "/api/login", 400, {"email": "", "password": ""})),
        ("Password at minimum length", "6-character password (valid format, wrong value)",
         "Passes validation but credentials rejected (401)", "boundary",
         _api("POST", "/api/login", 401, {"email": "tester@shop.com", "password": "Ab@123"})),
        ("Password below minimum length", "5-character password", "Validation message displayed (400)", "boundary",
         _api("POST", "/api/login", 400, {"email": "tester@shop.com", "password": "Ab@12"})),
    ]


def _search_cases():
    return [
        ("Search with matching keyword", "Keyword 'laptop'", "Only laptop products listed", "positive",
         _api("GET", "/api/products?q=laptop", 200, None, min_items=1)),
        ("Search with no match", "Keyword 'zzzz'", "Empty result list", "negative",
         _api("GET", "/api/products?q=zzzz", 200, None, max_items=0)),
        ("Search with empty keyword", "Blank keyword", "All products listed", "boundary",
         _api("GET", "/api/products?q=", 200, None, min_items=8)),
        ("Search is case-insensitive", "Keyword 'LAPTOP'", "Same results as 'laptop'", "positive",
         _api("GET", "/api/products?q=LAPTOP", 200, None, min_items=1)),
    ]


def _cart_cases():
    return [
        ("Add product to cart", "Click 'Add to cart' on one product", "Cart counter increases by 1", "positive", None),
        ("Cart total calculation", "Add two different products", "Total equals the sum of both prices", "positive", None),
        ("Remove product from cart", "Remove the only product", "Cart shows it is empty", "positive", None),
        ("Add same product twice", "Add one product two times", "Quantity becomes 2", "boundary", None),
    ]


def _checkout_cases():
    return [
        ("Checkout with valid details", "Name and a full address", "Order confirmation is shown", "positive", None),
        ("Checkout with invalid address", "Address 'abc'", "Validation error, order not placed", "negative", None),
        ("Checkout with empty name", "Blank full name", "Validation error, order not placed", "negative", None),
        ("Address at minimum length", "Address with exactly 10 characters", "Order accepted", "boundary", None),
    ]


KEYWORDS = [
    (("login", "log in", "sign in", "password", "email"), _login_cases),
    (("search", "find product", "browse"), _search_cases),
    (("cart", "basket"), _cart_cases),
    (("checkout", "address", "order", "payment"), _checkout_cases),
]


def offline_cases(story):
    text = story.lower()
    rows = []
    for words, factory in KEYWORDS:
        if any(w in text for w in words):
            rows += factory()
    if not rows:
        rows = [
            ("Main flow works", f"Valid input for: {story[:80]}", "Feature behaves as described", "positive", None),
            ("Invalid input rejected", "Missing or malformed input", "Clear validation message", "negative", None),
            ("Limits enforced", "Minimum and maximum allowed values", "Boundaries behave as specified", "boundary", None),
        ]
    return [dict(scenario=s, input=i, expected=e, kind=k, api_spec=a) for s, i, e, k, a in rows]


def _valid_spec(spec):
    if not isinstance(spec, dict):
        return None
    if spec.get("method") not in ("GET", "POST", "PUT", "DELETE"):
        return None
    if not str(spec.get("path", "")).startswith("/api/") or not isinstance(spec.get("status"), int):
        return None
    return spec


def llm_cases(story):
    raw = ask(story, SYSTEM, 3000)
    if not raw:
        return None
    try:
        data = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
        cases = [dict(scenario=str(d["scenario"]), input=str(d["input"]), expected=str(d["expected"]),
                      kind=d.get("kind", "positive"), api_spec=_valid_spec(d.get("api_spec")))
                 for d in data]
        return cases or None
    except (ValueError, KeyError, TypeError):
        return None


def generate_cases(story):
    """Returns (cases, source) where source is 'LLM' or 'offline rules'."""
    cases = llm_cases(story)
    if cases:
        return cases, "LLM"
    return offline_cases(story), "offline rules"


if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "As a user, I want to log in using my email and password."
    result, src = generate_cases(text)
    print(f"Generated {len(result)} cases using {src}")
    for n, c in enumerate(result, 1):
        print(f"TC{n:03d} | {c['scenario']} | {c['input']} | {c['expected']}")
