![CI](https://github.com/sanesh2310-png/ai-continuous-testing-framework/actions/workflows/ci.yml/badge.svg)

# Intelligent Continuous Testing Framework for Web Applications Using AI and CI/CD

A QA platform that **generates test cases from requirements (AI), runs automated UI + API tests,
shows pass/fail results with screenshots, analyses failures, and displays the real GitHub Actions
pipeline status**. When code is pushed to GitHub, the pipeline tests it automatically and blocks
deployment if tests fail.

```
 requirement ──► AI Test Generator ──► approve ──► generated PyTest scripts
                                                          │
 developer push ─► GitHub Actions: Build ─► API tests ─► UI tests ─► Deploy (blocked on failure)
                                                          │
 QA Dashboard (Flask, :5001) ◄── runs PyTest, stores results (SQLite), reads GitHub Actions status
        │
        └─► Dashboard · AI Generator · Execution · Bug Analysis · CI/CD · Reports
```

Roles of each part: **Flask dashboard** = interface to manage/view tests · **PyTest + Selenium** = performs the
tests · **GitHub Actions** = the actual CI/CD engine · **ShopEasy** = the application being tested.

## Project layout
```
shop/            ShopEasy e-commerce app under test (login, search, cart, checkout, JSON API)
tests/api/       API tests (PyTest + Flask test client)
tests/ui/        Selenium tests + pages/ (Page Object Model)
tests/generated/ scripts generated from approved AI test cases (created by the dashboard)
dashboard/       QA dashboard (6 pages)      ai/   LLM client, case generator, CI failure summariser
postman/         Postman collection (run with Newman)
.github/workflows/ci.yml   Build -> API tests -> UI tests -> Deploy
Dockerfile, Dockerfile.tests, docker-compose.yml
```

## Setup (VS Code terminal, Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Mac/Linux: `source .venv/bin/activate`. UI tests need Google Chrome (or Firefox) installed; Selenium downloads the driver itself. Use `BROWSER=firefox` or the Browser dropdown on the Test Execution page to run in Firefox.

## Run the QA dashboard
```powershell
python -m dashboard.app          # open http://127.0.0.1:5001
```
1. **Dashboard** – metrics from the latest run, recent failures, history, buttons.
2. **AI Test Generator** – paste a user story, generate, edit, approve, export CSV/Excel,
   *Convert to automation* (writes `tests/generated/test_generated_cases.py`).
3. **Test Execution** – choose scope, tick *Simulate defects* to see failures, click *Run tests*.
4. **Bug Analysis** – expected vs actual, reason, severity, category, screenshot, suggested action.
5. **CI/CD Pipeline** – real GitHub Actions runs and stages (needs `.env`, see below).
6. **Reports & Analytics** – pass/fail chart, build comparison, frequently failing tests,
   regression results, downloadable HTML report (Print → Save as PDF for PDF).

Try the shop itself: `python -m shop.app` → http://localhost:5000 (login `tester@shop.com` / `Test@123`).

## Run tests from the command line
```powershell
pytest tests/api                 # fast, no browser
pytest tests/ui                  # Selenium (Chrome). $env:HEADED=1 to watch it
pytest                           # everything
$env:SHOP_BUGS="checkout_address,api_login"; pytest   # run against the deliberately broken shop
npx newman run postman/shopeasy.postman_collection.json   # needs `python -m shop.app` running
```

## Connect GitHub Actions to the dashboard
1. Create an empty repository on GitHub and push this project to it (the **CI/CD Pipeline** page shows the exact commands):
   `git init`, `git add .`, `git commit -m "QA automation framework"`, `git branch -M main`,
   `git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git`, `git push -u origin main`.
2. Open the dashboard → **CI/CD Pipeline** → type `YOUR-USERNAME/YOUR-REPO` → **Connect**.
   (If the project is already pushed, the dashboard detects the repository from the git remote by itself.
   For a private repository also paste a GitHub token with read access to the repository and Actions.)
3. GitHub starts the pipeline on every push; its stages appear on the CI/CD page and the Dashboard.
4. Optional secrets (GitHub → Settings → Secrets → Actions): `ANTHROPIC_API_KEY` (AI failure summary in CI) and
   `RENDER_DEPLOY_HOOK_URL` (real deployment on Render).

## AI features (work offline too)
Set `ANTHROPIC_API_KEY` in `.env` to use an LLM. Without it:
- test generation uses built-in rules (login, search, cart, checkout stories),
- failure suggestions are rule-based.
Suggestions are always labelled as hypotheses, never confirmed diagnoses.

## Presentation script
1. Open the dashboard → show metrics. 2. AI Test Generator → enter the login story → generate →
approve → convert. 3. Test Execution → run API tests → show passes. 4. Tick *Simulate defects* → run → show
failures, screenshot (UI) and Bug Analysis. 5. In `shop/app.py` break the login check (e.g. make
`credentials_ok` always return `True`), commit and push. 6. CI/CD page → Actions run fails, **Deployment = Blocked**.
7. Revert the change, push → pipeline passes, deployment runs. 8. Reports page → compare builds.

## Docker (optional)
```powershell
docker compose up --build app                                    # the shop on :5000
docker compose --profile test up --build --exit-code-from tests  # shop + Selenium + UI tests
```
The dashboard runs locally (it needs your Chrome); only the shop and test runner are containerised.

## Known limits
- Dashboard "Automation coverage" = approved cases converted to executable scripts ÷ approved cases.
- UI-only generated cases become skeletons (shown as Skipped) that you complete by hand.
- The dashboard runs one test run at a time and is meant for local use (no login).
