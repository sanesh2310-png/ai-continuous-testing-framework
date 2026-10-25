"""Real GitHub Actions status.

The repository is found automatically from (1) GITHUB_REPO in .env or (2) the
`origin` remote of this project's git repository. A token is only needed for
private repositories or to avoid GitHub's anonymous rate limit.
Nothing is faked: if GitHub cannot be reached the page says why."""
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_cache = {}


def parse_repo(text):
    text = (text or "").strip()
    m = re.search(r"github\.com[:/]+([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return text if re.fullmatch(r"[\w.-]+/[\w.-]+", text) else None


def detect_repo():
    """Returns (owner/repo or None, source) where source is 'settings' or 'git'."""
    env = os.environ.get("GITHUB_REPO", "").strip()
    if env:
        return parse_repo(env) or env, "settings"
    try:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=ROOT,
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        url = ""
    repo = parse_repo(url)
    return (repo, "git") if repo else (None, None)


def _get(url, ttl=20, token=None):
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "qa-dashboard"}
    token = token or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=8) as r:
        data = json.load(r)
    _cache[url] = (time.time(), data)
    return data


def explain(exc):
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404:
            return "Repository not found. Check the name, or add a GitHub token if the repository is private."
        if exc.code == 401:
            return "GitHub rejected the token. Create a new token with read access to the repository and Actions."
        if exc.code == 403:
            return "GitHub's request limit was reached. Add a GitHub token (Connect GitHub) to continue."
    return f"Could not reach GitHub: {exc}"


def label(status, conclusion):
    if status != "completed":
        return "Running" if status == "in_progress" else "Queued"
    return {"success": "Success", "failure": "Failed", "skipped": "Blocked",
            "cancelled": "Cancelled"}.get(conclusion, (conclusion or "Unknown").capitalize())


def write_env(**values):
    path = ROOT / ".env"
    lines = path.read_text().splitlines() if path.exists() else []
    for key, value in values.items():
        new = f"{key}={value}"
        for i, line in enumerate(lines):
            if line.split("=", 1)[0].strip() == key:
                lines[i] = new
                break
        else:
            lines.append(new)
        os.environ[key] = value
    path.write_text("\n".join(lines) + "\n")


def connect(repo_text, token=""):
    """Validates the repository against GitHub, then saves it. Returns (ok, message)."""
    repo = parse_repo(repo_text)
    if not repo:
        return False, "Enter the repository as owner/repo or paste its GitHub URL."
    try:
        _get(f"https://api.github.com/repos/{repo}", ttl=0, token=token.strip() or None)
    except Exception as exc:
        return False, explain(exc)
    write_env(GITHUB_REPO=repo, **({"GITHUB_TOKEN": token.strip()} if token.strip() else {}))
    _cache.clear()
    return True, f"Connected to {repo}."


def disconnect():
    write_env(GITHUB_REPO="", GITHUB_TOKEN="")
    _cache.clear()


def pipeline_status(selected_run=None):
    repo, source = detect_repo()
    if not repo:
        return {"configured": False}
    out = {"configured": True, "repo": repo, "source": source, "repo_url": f"https://github.com/{repo}",
           "actions_url": f"https://github.com/{repo}/actions", "runs": [], "jobs": [], "error": None,
           "success_rate": None, "selected": None}
    try:
        raw = _get(f"https://api.github.com/repos/{repo}/actions/runs?per_page=10")["workflow_runs"]
        for r in raw:
            out["runs"].append({
                "id": r["id"], "number": r["run_number"], "branch": r["head_branch"], "event": r["event"],
                "label": label(r["status"], r["conclusion"]), "sha": r["head_sha"][:7],
                "message": (r.get("display_title") or "")[:70], "created": r["created_at"].replace("T", " ")[:16],
                "url": r["html_url"],
            })
        done = [r for r in raw if r["status"] == "completed" and r["conclusion"] in ("success", "failure")]
        if done:
            out["success_rate"] = round(100 * sum(r["conclusion"] == "success" for r in done) / len(done), 1)
        if raw:
            rid = selected_run or raw[0]["id"]
            out["selected"] = rid
            for j in _get(f"https://api.github.com/repos/{repo}/actions/runs/{rid}/jobs")["jobs"]:
                out["jobs"].append({
                    "name": j["name"], "label": label(j["status"], j["conclusion"]),
                    "steps": [{"name": s["name"], "label": label(s["status"], s["conclusion"])}
                              for s in j.get("steps", [])],
                })
    except Exception as exc:
        out["error"] = explain(exc)
    out["active"] = any(r["label"] in ("Running", "Queued") for r in out["runs"])
    return out
