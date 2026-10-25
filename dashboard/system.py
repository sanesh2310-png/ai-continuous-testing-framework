"""Environment checks shown on the dashboard so problems are visible before a run."""
import os
import shutil

from . import db, github

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
FIREFOX_PATHS = [
    r"C:\Program Files\Mozilla Firefox\firefox.exe",
    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    "/Applications/Firefox.app/Contents/MacOS/firefox",
]


def browsers():
    chrome = any(shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium",
                                           "chromium-browser", "chrome")) or any(os.path.exists(p) for p in CHROME_PATHS)
    firefox = bool(shutil.which("firefox")) or any(os.path.exists(p) for p in FIREFOX_PATHS) \
        or bool(os.environ.get("FIREFOX_BINARY") and os.path.exists(os.environ["FIREFOX_BINARY"]))
    return {"chrome": chrome, "firefox": firefox}


def default_browser():
    b = browsers()
    return "firefox" if (b["firefox"] and not b["chrome"]) else "chrome"


def checks():
    b = browsers()
    repo, source = github.detect_repo()
    git_repo = (db.ROOT / ".git").exists()
    items = []
    if b["chrome"] or b["firefox"]:
        found = " and ".join(n.capitalize() for n in ("chrome", "firefox") if b[n])
        items.append(("ok", "Browser for UI tests", f"{found} found"))
    else:
        items.append(("warn", "Browser for UI tests", "Install Google Chrome to run the Selenium UI tests (API tests work without it)"))
    items.append(("ok" if repo else "warn", "GitHub repository",
                  f"{repo} ({'from git remote' if source == 'git' else 'from settings'})" if repo
                  else "Not connected - open the CI/CD Pipeline page to connect"))
    items.append(("ok" if git_repo else "warn", "Git version control",
                  "This project is a git repository" if git_repo else "Not a git repository yet - see the CI/CD page for the push commands"))
    items.append(("ok" if os.environ.get("ANTHROPIC_API_KEY") else "info", "AI test generation",
                  "LLM enabled" if os.environ.get("ANTHROPIC_API_KEY")
                  else "Using built-in rules (add ANTHROPIC_API_KEY to .env for LLM generation)"))
    return items
