"""Failure analysis: category, severity and a *suggested* cause/fix.

Suggestions are hints, not confirmed diagnoses. A failing test can also mean the
test or the environment is wrong."""
import json

from ai.llm import ask

RULES = {
    "Input Validation": "Validate the input on the server before processing it and return a clear error message.",
    "Authentication": "Review the credential check in the login function; wrong credentials must be rejected (HTTP 401 / error message).",
    "Search": "Check the search filter logic (case handling, empty keyword, no-match response).",
    "Cart": "Check how cart quantities and totals are calculated and stored in the session.",
    "Checkout": "Check the order-placement flow and its validation rules.",
    "API": "Compare the endpoint's status code and response body with the API specification.",
    "Environment": "The test could not run. Check that Chrome is installed and the network is available, then re-run. Probably not an application bug.",
}
DEFAULT_RULE = "Reproduce the failure manually, then compare the actual and expected behaviour to locate the faulty step."

PROMPT = ("You are a QA lead. For each failed test below give ONE sentence: the most likely cause and a fix. "
          "Reply ONLY as JSON object mapping the index (string) to the sentence. These are hypotheses.\n\n")


def _llm(failures):
    listing = "\n".join(f"{i}: {f['tc_id']} {f['name']} | expected: {f['expected']} | actual: {f['actual']}"
                        for i, f in enumerate(failures))
    raw = ask(PROMPT + listing, "", 1200)
    if not raw:
        return {}
    try:
        return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        return {}


def analyze(failures):
    """failures: list of result dicts. Fills severity, category, suggestion(+source) in place."""
    ai = _llm(failures) if failures else {}
    for i, f in enumerate(failures):
        if f["status"] == "error":
            f["category"] = "Environment"
        f["category"] = f.get("category") or "Functional"
        f["severity"] = f.get("severity") or ("Medium" if f["category"] == "Environment" else "High")
        if str(i) in ai:
            f["suggestion"], f["suggestion_source"] = ai[str(i)], "AI"
        else:
            f["suggestion"], f["suggestion_source"] = RULES.get(f["category"], DEFAULT_RULE), "rule-based"
    return failures
