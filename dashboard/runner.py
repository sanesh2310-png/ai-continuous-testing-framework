"""Runs PyTest in a background thread and stores the outcome in SQLite."""
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from . import analysis, db

RUNS_ROOT = db.ROOT / "reports" / "runs"
_lock = threading.Lock()
TARGETS = {"all": ["tests"], "ui": ["tests/ui"], "api": ["tests/api", "tests/generated"]}
BUGS = "checkout_address,api_login"


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def start_run(scope, inject_bugs, browser="chrome"):
    if scope not in TARGETS or not _lock.acquire(blocking=False):
        return None
    run_id = db.execute("INSERT INTO runs (started_at, scope, bugs, status) VALUES (?,?,?,'running')",
                        (now(), scope, int(inject_bugs)))
    threading.Thread(target=_work, args=(run_id, scope, inject_bugs, browser), daemon=True).start()
    return run_id


def _work(run_id, scope, inject_bugs, browser):
    started = time.time()
    run_dir = RUNS_ROOT / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    results_file = run_dir / "results.json"
    env = {**os.environ, "RUN_DIR": str(run_dir), "RESULTS_JSON": str(results_file),
           "SHOP_BUGS": BUGS if inject_bugs else "",
           "BROWSER": browser if browser in ("chrome", "firefox") else "chrome"}
    cmd = [sys.executable, "-m", "pytest", *TARGETS[scope], "-q", "-p", "no:cacheprovider",
           f"--junitxml={run_dir / 'junit.xml'}"]
    output = ""
    try:
        proc = subprocess.run(cmd, cwd=db.ROOT, env=env, capture_output=True, text=True, timeout=900)
        output = (proc.stdout + proc.stderr)[-20000:]
        results = json.loads(results_file.read_text()) if results_file.exists() else []
        status = "finished"
    except Exception as exc:  # timeout, missing pytest...
        results, status, output = [], "error", f"Run failed: {exc}"
    try:
        _store(run_id, results, status, output, time.time() - started)
    finally:
        _lock.release()


def _store(run_id, results, status, output, duration):
    stamp = now()
    failures = [r for r in results if r["status"] in ("failed", "error")]
    analysis.analyze(failures)
    rows = []
    for r in results:
        shot = ""
        if r.get("screenshot"):
            try:
                shot = Path(r["screenshot"]).resolve().relative_to(RUNS_ROOT.resolve()).as_posix()
            except ValueError:
                shot = ""
        rows.append((run_id, r["tc_id"], r["name"], r["suite"], r["status"], r["duration"], r["expected"],
                     r["actual"], r["reason"], r.get("severity", ""), r.get("category", ""), shot,
                     r.get("suggestion", ""), r.get("suggestion_source", ""), stamp))
    db.executemany("INSERT INTO results (run_id,tc_id,name,suite,status,duration,expected,actual,reason,"
                   "severity,category,screenshot,suggestion,suggestion_source,timestamp) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    passed = sum(r["status"] == "passed" for r in results)
    skipped = sum(r["status"] == "skipped" for r in results)
    db.execute("UPDATE runs SET status=?, duration=?, total=?, passed=?, failed=?, skipped=?, output=? WHERE id=?",
               (status, round(duration, 1), len(results), passed, len(failures), skipped, output, run_id))
