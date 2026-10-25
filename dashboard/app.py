"""QA dashboard: generate test cases, run tests, inspect failures, view CI/CD + reports."""
import base64
import csv
import io
import json
import os
from collections import Counter
from datetime import datetime

from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, url_for)

from ai.case_generator import generate_cases

from . import converter, db, github, runner, system


def load_env_file():
    path = db.ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def pct(part, whole):
    return round(100 * part / whole, 2) if whole else 0.0


def latest_run(only_finished=True):
    sql = "SELECT * FROM runs " + ("WHERE status='finished' " if only_finished else "") + "ORDER BY id DESC LIMIT 1"
    return db.one(sql)


def run_results(run_id):
    return db.query("SELECT * FROM results WHERE run_id=? ORDER BY id", (run_id,))


def console_text(run, results):
    lines = ["AUTOMATED TEST EXECUTION", "",
             "Application: ShopEasy (e-commerce website)", "Framework: Selenium + PyTest", ""]
    tag = {"passed": "PASS", "failed": "FAIL", "error": "ERROR", "skipped": "SKIP"}
    lines += [f"[{tag.get(r['status'], r['status'].upper())}] {r['name']}" for r in results]
    lines += ["", f"Total Tests: {run['total']}", f"Passed: {run['passed']}", f"Failed: {run['failed']}",
              f"Skipped: {run['skipped']}", f"Pass Rate: {pct(run['passed'], run['total']):.2f}%",
              f"Execution Time: {run['duration']} seconds"]
    return "\n".join(lines)


def regression(latest_id):
    prev = db.one("SELECT id FROM runs WHERE status='finished' AND id<? AND scope=(SELECT scope FROM runs WHERE id=?)"
                  " ORDER BY id DESC LIMIT 1", (latest_id, latest_id))
    if not prev:
        return None
    key = lambda r: (r["suite"], r["tc_id"], r["name"])
    old = {key(r): r["status"] for r in run_results(prev["id"])}
    new = {key(r): r["status"] for r in run_results(latest_id)}
    bad = ("failed", "error")
    return {
        "previous": prev["id"],
        "regressions": [k[2] for k in new if new[k] in bad and old.get(k) == "passed"],
        "fixed": [k[2] for k in new if new[k] == "passed" and old.get(k) in bad],
        "still_failing": [k[2] for k in new if new[k] in bad and old.get(k) in bad],
    }


EXAMPLES = [
    ("Login", "As a user, I want to log in using my email and password so that I can access my account."),
    ("Product search", "As a customer, I want to search for products by name so that I can find what I need quickly."),
    ("Cart", "As a customer, I want to add products to my cart and see the total so that I can review my order."),
    ("Checkout", "As a customer, I want to enter my name and delivery address at checkout so that my order can be placed."),
]


def create_app():
    load_env_file()
    app = Flask(__name__)
    app.secret_key = os.environ.get("DASHBOARD_SECRET", "dashboard-dev")
    db.init()
    app.jinja_env.filters["pct"] = lambda v: f"{v:.2f}%"
    app.jinja_env.globals["pct_of"] = pct

    # ------------------------------ 1. dashboard ------------------------------
    @app.route("/")
    def dashboard():
        run = latest_run()
        results = run_results(run["id"]) if run else []
        history = db.query("SELECT * FROM runs WHERE status!='running' ORDER BY id DESC LIMIT 8")
        approved = db.one("SELECT COUNT(*) n FROM cases WHERE approved=1")["n"]
        automated = db.one("SELECT COUNT(*) n FROM cases WHERE approved=1 AND automated=1")["n"]
        pipeline = github.pipeline_status()
        latest_pipe = pipeline["runs"][0]["label"] if pipeline.get("runs") else None
        return render_template(
            "dashboard.html", run=run, history=history,
            failures=[r for r in results if r["status"] in ("failed", "error")][:5],
            pass_rate=pct(run["passed"], run["total"]) if run else 0,
            coverage=pct(automated, approved) if approved else None, approved=approved, automated=automated,
            pipeline=pipeline, latest_pipe=latest_pipe, checks=system.checks(),
            browser=system.default_browser(),
            running=db.one("SELECT id FROM runs WHERE status='running'"))

    # ------------------------------ 2. AI generator ------------------------------
    @app.route("/generate", methods=["GET", "POST"])
    def generate():
        if request.method == "POST":
            story = request.form.get("story", "").strip()
            if len(story) < 10:
                flash("Enter a requirement or user story (at least 10 characters).", "error")
                return redirect(url_for("generate"))
            cases, source = generate_cases(story)
            batch = datetime.now().strftime("%Y%m%d%H%M%S")
            base = db.one("SELECT COUNT(*) n FROM cases")["n"]
            db.executemany(
                "INSERT INTO cases (batch,story,tc_id,scenario,input,expected,kind,api_spec,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                [(batch, story, f"TC{base + i:03d}", c["scenario"], c["input"], c["expected"], c["kind"],
                  json.dumps(c["api_spec"]) if c["api_spec"] else None,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")) for i, c in enumerate(cases, 1)])
            flash(f"Generated {len(cases)} test cases using {source}. Review, edit and approve them below.", "success")
            return redirect(url_for("generate"))
        return render_template("generate.html", cases=db.query("SELECT * FROM cases ORDER BY id DESC LIMIT 200"),
                               example=EXAMPLES[0][1], examples=EXAMPLES)

    @app.post("/cases/action")
    def cases_action():
        ids = [int(i) for i in request.form.getlist("selected")]
        for row in db.query("SELECT id FROM cases ORDER BY id DESC LIMIT 200"):  # save inline edits
            cid = row["id"]
            if f"scenario_{cid}" in request.form:
                db.execute("UPDATE cases SET scenario=?, input=?, expected=? WHERE id=?",
                           (request.form[f"scenario_{cid}"], request.form[f"input_{cid}"],
                            request.form[f"expected_{cid}"], cid))
        action = request.form.get("action")
        if action in ("approve", "unapprove", "delete", "convert") and not ids:
            flash("Select at least one test case first.", "error")
        elif action == "approve":
            db.executemany("UPDATE cases SET approved=1 WHERE id=?", [(i,) for i in ids])
            flash(f"Approved {len(ids)} test case(s).", "success")
        elif action == "unapprove":
            db.executemany("UPDATE cases SET approved=0, automated=0 WHERE id=?", [(i,) for i in ids])
            flash(f"Moved {len(ids)} test case(s) back to draft.", "success")
        elif action == "delete":
            db.executemany("DELETE FROM cases WHERE id=?", [(i,) for i in ids])
            flash(f"Deleted {len(ids)} test case(s).", "success")
        elif action == "convert":
            ok = [i for i in ids if db.one("SELECT 1 FROM cases WHERE id=? AND approved=1", (i,))]
            if not ok:
                flash("Only approved test cases can be converted. Approve them first.", "error")
            else:
                ex, sk = converter.convert(ok)
                flash(f"Wrote tests/generated/test_generated_cases.py: {ex} executable test(s), "
                      f"{sk} skeleton(s) that need manual steps.", "success")
        elif action == "save":
            flash("Edits saved.", "success")
        return redirect(url_for("generate"))

    @app.route("/cases/export.<fmt>")
    def export_cases(fmt):
        rows = db.query("SELECT tc_id, scenario, input, expected, kind, approved, automated FROM cases ORDER BY id")
        head = ["Test ID", "Test Scenario", "Input", "Expected Result", "Type", "Approved", "Automation"]
        data = [[r["tc_id"], r["scenario"], r["input"], r["expected"], r["kind"],
                 "yes" if r["approved"] else "no",
                 {0: "none", 1: "executable", 2: "skeleton"}[r["automated"]]] for r in rows]
        if fmt == "csv":
            buf = io.StringIO()
            csv.writer(buf).writerows([head] + data)
            return Response(buf.getvalue(), mimetype="text/csv",
                            headers={"Content-Disposition": "attachment; filename=test_cases.csv"})
        if fmt == "xlsx":
            try:
                from openpyxl import Workbook
            except ImportError:
                return Response("Install openpyxl (pip install openpyxl) to export Excel.", status=501)
            wb = Workbook()
            ws = wb.active
            ws.title = "Test cases"
            for row in [head] + data:
                ws.append(row)
            out = io.BytesIO()
            wb.save(out)
            return Response(out.getvalue(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            headers={"Content-Disposition": "attachment; filename=test_cases.xlsx"})
        abort(404)

    # ------------------------------ 3. execution ------------------------------
    @app.route("/execute")
    def execute():
        run = db.one("SELECT * FROM runs WHERE id=?", (request.args.get("run", type=int),)) if request.args.get("run") \
            else latest_run(only_finished=False)
        results = run_results(run["id"]) if run else []
        return render_template("execute.html", run=run, results=results, browsers=system.browsers(),
                               browser=system.default_browser(),
                               console=console_text(run, results) if run and run["status"] != "running" else "",
                               failures=[r for r in results if r["status"] in ("failed", "error")],
                               running=db.one("SELECT id FROM runs WHERE status='running'"))

    @app.post("/run")
    def run_tests():
        run_id = runner.start_run(request.form.get("scope", "all"), request.form.get("bugs") == "on",
                                  request.form.get("browser", "chrome"))
        if not run_id:
            flash("A test run is already in progress (or the scope is invalid).", "error")
            return redirect(url_for("execute"))
        return redirect(url_for("execute", run=run_id))

    @app.get("/api/run/<int:run_id>")
    def run_status(run_id):
        row = db.one("SELECT id, status FROM runs WHERE id=?", (run_id,))
        return jsonify(dict(row)) if row else (jsonify(error="not found"), 404)

    @app.get("/screenshots/<path:rel>")
    def screenshot(rel):
        return send_from_directory(runner.RUNS_ROOT, rel)

    # ------------------------------ 4. bug analysis ------------------------------
    @app.route("/bugs")
    def bugs():
        runs = db.query("SELECT id, started_at FROM runs WHERE status='finished' ORDER BY id DESC LIMIT 20")
        run_id = request.args.get("run", type=int) or (runs[0]["id"] if runs else None)
        failures = db.query("SELECT * FROM results WHERE run_id=? AND status IN ('failed','error') ORDER BY id",
                            (run_id,)) if run_id else []
        return render_template("bugs.html", runs=runs, run_id=run_id, failures=failures)

    # ------------------------------ 5. pipeline ------------------------------
    @app.route("/pipeline")
    def pipeline():
        p = github.pipeline_status(request.args.get("run", type=int))
        return render_template("pipeline.html", p=p, git_repo=(db.ROOT / ".git").exists())

    @app.post("/pipeline/connect")
    def pipeline_connect():
        ok, message = github.connect(request.form.get("repo", ""), request.form.get("token", ""))
        flash(message, "success" if ok else "error")
        return redirect(url_for("pipeline"))

    @app.post("/pipeline/disconnect")
    def pipeline_disconnect():
        github.disconnect()
        flash("GitHub disconnected.", "success")
        return redirect(url_for("pipeline"))

    # ------------------------------ 6. reports ------------------------------
    @app.route("/reports")
    def reports():
        runs = list(reversed(db.query("SELECT * FROM runs WHERE status='finished' ORDER BY id DESC LIMIT 10")))
        latest = runs[-1] if runs else None
        frequent = db.query("SELECT tc_id, name, COUNT(*) n FROM results WHERE status IN ('failed','error') "
                            "GROUP BY tc_id, name ORDER BY n DESC LIMIT 5")
        return render_template("reports.html", runs=runs, latest=latest, frequent=frequent,
                               reg=regression(latest["id"]) if latest else None,
                               pipeline=github.pipeline_status())

    @app.route("/reports/download/<int:run_id>")
    def download_report(run_id):
        run = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
        if not run:
            abort(404)
        results = run_results(run_id)
        shots = {}
        for r in results:
            if r["screenshot"]:
                try:
                    with open(runner.RUNS_ROOT / r["screenshot"], "rb") as fh:
                        shots[r["id"]] = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
                except OSError:
                    pass
        html = render_template("report.html", run=run, results=results, shots=shots,
                               rate=pct(run["passed"], run["total"]), console=console_text(run, results))
        return Response(html, mimetype="text/html",
                        headers={"Content-Disposition": f"attachment; filename=qa_report_run_{run_id}.html"})

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("DASHBOARD_PORT", 5001)))
