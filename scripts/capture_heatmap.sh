#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
OUT="${OUT:-artifacts/heatmap-mvp.png}"

mkdir -p "$(dirname "$OUT")"

python - <<'PY'
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base_url = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
out = os.environ.get("OUT", "artifacts/heatmap-mvp.png")

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    print("playwright niet gevonden. Installeer met: pip install playwright && python -m playwright install chromium", file=sys.stderr)
    sys.exit(2)


def post(path: str, payload: dict, token: str | None = None):
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        f"{base_url}{path}",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"POST {path} failed: HTTP {exc.code}") from exc


# 1) Login token ophalen
login = post("/auth/token", {"username": "planner", "password": "planner123"})
token = login["access_token"]

# 2) Demo-data opzetten (1 beschikbaar + 1 afwezig, 2 overlappende shifts)
post(
    "/employees",
    {
        "id": "shot_e_available",
        "team_id": "shot_team",
        "site_id": "shot_site",
        "skills": ["operator"],
        "available": True,
    },
    token,
)
post(
    "/employees",
    {
        "id": "shot_e_absent",
        "team_id": "shot_team",
        "site_id": "shot_site",
        "skills": ["operator"],
        "available": False,
    },
    token,
)

base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
start_iso = base.isoformat()
end_iso = (base + timedelta(hours=1)).isoformat()
for i in range(2):
    post(
        "/shifts",
        {
            "id": f"shot_s_{i}",
            "team_id": "shot_team",
            "site_id": "shot_site",
            "required_skill": "operator",
            "start": start_iso,
            "end": end_iso,
        },
        token,
    )

# 3) UI openen, login doen en heatmap laden
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    page.goto(base_url, wait_until="networkidle")

    page.fill("#username", "planner")
    page.fill("#password", "planner123")
    page.click("#login-btn")
    page.wait_for_timeout(600)

    page.fill("#heatmap-team", "shot_team")
    page.fill("#heatmap-site", "shot_site")

    def to_local_input(dt: datetime):
        local = dt.astimezone()
        return local.strftime("%Y-%m-%dT%H:%M")

    page.fill("#heatmap-start", to_local_input(base))
    page.fill("#heatmap-end", to_local_input(base + timedelta(hours=2)))
    page.click("#heatmap-btn")

    page.wait_for_selector("#heatmap-grid .heatmap-cell", timeout=15000)
    page.screenshot(path=out, full_page=True)
    browser.close()

print(f"Screenshot geschreven naar: {out}")
PY
