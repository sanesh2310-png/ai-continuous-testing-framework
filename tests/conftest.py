"""Shared fixtures + a small reporting plugin.

The plugin records every test (id, name, expected, actual, failure reason,
screenshot...) into $RESULTS_JSON when that variable is set. The QA dashboard
sets it for each run and reads the file afterwards.
"""
import json
import os
import re
from pathlib import Path

import pytest

from shop.app import create_app

_RESULTS = []


@pytest.fixture
def client():
    """Flask test client for the shop (honours SHOP_BUGS)."""
    return create_app({"TESTING": True}).test_client()


def _meta(item):
    marker = item.get_closest_marker("case")
    args = marker.args if marker else ()
    kw = marker.kwargs if marker else {}
    suite = "UI" if "tests/ui" in item.nodeid.replace("\\", "/") else "API"
    return {
        "tc_id": args[0] if len(args) > 0 else item.name,
        "name": args[1] if len(args) > 1 else item.name.replace("_", " "),
        "suite": suite,
        "expected": kw.get("expected", ""),
        "category": kw.get("category", ""),
        "severity": kw.get("severity", ""),
    }


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    report.case_meta = _meta(item)
    report.screenshot = ""
    report.page = ""
    drv = item.funcargs.get("driver")
    if drv and report.when == "call" and report.failed:
        try:
            report.page = drv.current_url
        except Exception:
            pass
        shots = Path(os.environ.get("RUN_DIR", "reports")) / "screenshots"
        shots.mkdir(parents=True, exist_ok=True)
        path = shots / (re.sub(r"[^A-Za-z0-9_.-]+", "_", item.name) + ".png")
        try:
            drv.save_screenshot(str(path))
            report.screenshot = str(path)
        except Exception:
            pass


def pytest_runtest_logreport(report):
    interesting = report.when == "call" or (report.when == "setup" and report.outcome != "passed")
    if not interesting or not hasattr(report, "case_meta"):
        return
    meta = dict(report.case_meta)
    param = report.nodeid.split("[", 1)[1].rstrip("]") if "[" in report.nodeid else ""
    if param:
        meta["name"] += f" [{param}]"
    status = report.outcome
    if status == "failed" and report.when == "setup":
        status = "error"
    actual = reason = ""
    if report.failed:
        crash = getattr(report.longrepr, "reprcrash", None)
        message = (crash.message if crash else str(report.longrepr)).strip()
        first = message.splitlines()[0] if message else ""
        actual = re.sub(r"^\w*(Error|Exception):\s*", "", first) or first
        reason = f"{first[:160]}" + (f" (at {Path(crash.path).name}:{crash.lineno})" if crash else "")
        if getattr(report, "page", ""):
            reason += f" [browser was on {report.page}]"
        if report.when == "setup":
            meta["category"] = "Environment"
    elif report.skipped:
        lr = report.longrepr
        actual = lr[2] if isinstance(lr, tuple) and len(lr) > 2 else "skipped"
    _RESULTS.append({**meta, "nodeid": report.nodeid, "status": status,
                     "duration": round(report.duration, 3), "actual": actual,
                     "reason": reason, "screenshot": report.screenshot,
                     "timestamp": ""})


def pytest_sessionfinish(session):
    out = os.environ.get("RESULTS_JSON")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(_RESULTS, indent=2))
