# EKAP Complaint Monitor

Automated watcher for appeal complaint filings (*itirazen şikayet başvurusu*) on Turkey's Public Procurement Authority portal ([EKAP](https://ekapv2.kik.gov.tr)). When a new complaint appears on any tracked tender, an email alert is sent immediately.

Built for procurement professionals who need real-time visibility into competitor or supplier complaints without manually checking the portal multiple times a day.

---

## How it works

### Architecture

```
GitHub Actions (cron every 5 min)
        │
        ▼
  monitor.py runs
        │
        ├─► Playwright opens headless Chromium
        │         │
        │         └─► For each tender in TENDERS list:
        │               1. Navigate to EKAP query page
        │               2. Select year from DevExtreme dropdown
        │               3. Enter tender number, submit search
        │               4. Scrape complaint rows from data grid
        │
        ├─► Compare scraped rows against state.json
        │         │
        │         ├─ New complaints found → send email via Gmail SMTP
        │         └─ No change → skip silently
        │
        └─► Save updated state.json
                  │
                  └─► git-auto-commit pushes state.json back to repo
```

### Flow detail

1. **State load** — `state.json` is checked out from the repo and loaded. It holds the last-seen complaint rows for each tender ID.
2. **Scrape** — Playwright drives a headless Chromium browser, filling in the year and tender number fields on the EKAP search form (which uses DevExtreme components requiring real browser interaction).
3. **Diff** — Each scraped row is compared against the stored list. Any row not previously seen is flagged as new.
4. **Alert** — If any tender has new rows, one consolidated email is sent listing every new complaint with tender ID, total complaint count, and the raw row text.
5. **Persist** — Updated complaint lists are written back to `state.json`, which GitHub Actions then commits to the repository so state survives across runs.

---

## Setup

### Prerequisites

- Python 3.10+
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) (2-step verification must be enabled)
- A GitHub repository with Actions enabled

### Local installation

```bash
git clone <your-repo-url>
cd batu-app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Environment variables

| Variable | Description |
|---|---|
| `EMAIL_SENDER` | Gmail address used to send alerts (e.g. `alerts@gmail.com`) |
| `EMAIL_PASSWORD` | Gmail App Password (not your regular password) |

For local runs, export them in your shell:

```bash
export EMAIL_SENDER="your@gmail.com"
export EMAIL_PASSWORD="your-app-password"
python monitor.py
```

### GitHub Actions secrets

In your repository go to **Settings → Secrets and variables → Actions** and add:

- `EMAIL_SENDER`
- `EMAIL_PASSWORD`

The workflow reads these automatically. No other secrets are needed — `GITHUB_TOKEN` is provided by GitHub for the state commit step.

---

## Configuring which tenders to monitor

Edit the `TENDERS` list at the top of `monitor.py`:

```python
TENDERS = [
    {"year": "2026", "number": "444788"},
    {"year": "2026", "number": "598415"},
    # add or remove entries here
]
```

Each entry maps to a tender on EKAP identified by its year and ihale (procurement) number. To find the number, look up the tender on [EKAP](https://ekapv2.kik.gov.tr/sorgulamalar/itirazen-sikayet-basvurusu-sorgulama) and note the number shown in the search results.

To change the notification recipients, edit `EMAIL_RECEIVERS` in `monitor.py`:

```python
EMAIL_RECEIVERS = ["recipient1@example.com", "recipient2@example.com"]
```

---

## GitHub Actions scheduling

The workflow file is at `.github/workflows/monitor.yml`.

```yaml
on:
  schedule:
    - cron: '*/5 * * * *'   # runs every 5 minutes
  workflow_dispatch:          # also allows manual trigger from the Actions UI
```

**Note:** GitHub Actions cron jobs have a minimum granularity of 1 minute, but in practice free-tier runners may fire a few minutes late under load. For less time-sensitive monitoring, changing to `*/15 * * * *` (every 15 minutes) reduces runner usage and GitHub API load.

The workflow:
1. Checks out the repo (including the latest `state.json`)
2. Installs Python dependencies and Playwright's Chromium binary
3. Runs `monitor.py` with email credentials injected as environment variables
4. Commits any changes to `state.json` back to `main` using [git-auto-commit-action](https://github.com/stefanzweifel/git-auto-commit-action)

The commit step only fires when `state.json` actually changes (i.e., new complaints were found), so the git history stays clean.

---

## Example notification email

**Subject:** `EKAP Alert: 2 New/Updated Complaints`

```
Found updates for 2 tender(s):

--- Tender 2026/556654 (Total Complaints: 3 | New Updates: 1) ---
24.04.2026 11:29	Elekta Medikal Sistemler Tic. A.Ş.	

--- Tender 2026/444788 (Total Complaints: 2 | New Updates: 2) ---
13.04.2026 17:33	Elekta Medikal Sistemler Ticaret Anonim Şirketi	
12.04.2026 09:10	Some Other Company Ltd.	

Check at: https://ekapv2.kik.gov.tr/sorgulamalar/itirazen-sikayet-basvurusu-sorgulama
```

Each row contains the complaint filing date/time, the applicant company name, and any additional columns the EKAP data grid returns.

---

## Tech stack

| Component | Technology |
|---|---|
| Browser automation | [Playwright](https://playwright.dev/python/) (headless Chromium) |
| Email delivery | Python `smtplib` over Gmail SMTP (TLS, port 587) |
| State persistence | `state.json` committed to git via GitHub Actions |
| Scheduling | GitHub Actions `schedule` cron trigger |
| CI runner | `ubuntu-latest` (GitHub-hosted) |
| Language | Python 3.10+ |

The EKAP portal renders its search form with [DevExtreme](https://js.devexpress.com/) components, which require real DOM interaction (clicks, keyboard events) rather than simple HTTP requests. Playwright provides a full browser runtime that handles this correctly.
