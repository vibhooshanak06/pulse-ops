"""
Demo service setup script.

Provisions a dedicated PulseOps user, organization, project, and API key
for the demo service, then writes the key into demo-service/.env so the
SDK middleware picks it up automatically on next startup.

Run once before starting the demo service:
    python setup_demo.py

Safe to re-run — checks if the user already exists and skips registration
if so, then logs in and re-issues an API key.
"""

import re
import sys
import os
import httpx

BACKEND_URL   = "http://localhost:8000/v1"
ENV_FILE      = os.path.join(os.path.dirname(__file__), ".env")
SERVICE_NAME  = "demo-service"

DEMO_EMAIL    = "demo@pulseops.dev"
DEMO_PASSWORD = "DemoPass999"
DEMO_ORG      = "Demo Organization"
DEMO_PROJECT  = "demo-project"
DEMO_KEY_NAME = "Demo Service SDK Key"

c = httpx.Client(base_url=BACKEND_URL, timeout=10)


def banner(msg: str) -> None:
    print(f"\n{'='*55}\n  {msg}\n{'='*55}")


def step(label: str, ok: bool, detail: str = "") -> None:
    icon = "✓" if ok else "✗"
    print(f"  [{icon}] {label}" + (f"  →  {detail}" if detail else ""))
    if not ok:
        print("\nSetup failed. Check the backend is running on port 8000.")
        sys.exit(1)


# ── 1. Register or login ──────────────────────────────────────────────────────
banner("Step 1 — Authenticate")

r = c.post("/auth/register", json={
    "email":     DEMO_EMAIL,
    "password":  DEMO_PASSWORD,
    "full_name": "Demo User",
    "org_name":  DEMO_ORG,
})

if r.status_code == 201:
    TOKEN = r.json()["access_token"]
    step("Registered new demo user", True, DEMO_EMAIL)
elif r.status_code == 409:
    # User already exists — log in
    r2 = c.post("/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    step("Login (user already exists)", r2.status_code == 200, str(r2.status_code))
    TOKEN = r2.json()["access_token"]
else:
    step("Register/login", False, f"HTTP {r.status_code}: {r.text[:200]}")

H = {"Authorization": f"Bearer {TOKEN}"}
print(f"     token={TOKEN[:20]}...")

# ── 2. Resolve org ────────────────────────────────────────────────────────────
banner("Step 2 — Organization")

orgs = c.get("/organizations", headers=H).json()
step("Organizations loaded", len(orgs) > 0, f"found {len(orgs)}")
ORG_ID = orgs[0]["id"]
print(f"     org='{orgs[0]['name']}' ({ORG_ID[:8]}...)")

# ── 3. Get or create project ──────────────────────────────────────────────────
banner("Step 3 — Project")

projects = c.get(f"/organizations/{ORG_ID}/projects", headers=H).json()
existing = [p for p in projects if p["slug"] == DEMO_PROJECT]

if existing:
    PROJ_ID = existing[0]["id"]
    step("Project already exists", True, f"'{existing[0]['name']}'")
else:
    r = c.post(f"/organizations/{ORG_ID}/projects", headers=H,
               json={"name": "Demo Project", "slug": DEMO_PROJECT,
                     "description": "Project for the PulseOps demo service"})
    step("Project created", r.status_code == 201, str(r.status_code))
    PROJ_ID = r.json()["id"]

print(f"     project_id={PROJ_ID[:8]}...")

# ── 4. Create a fresh API key ─────────────────────────────────────────────────
banner("Step 4 — API Key")

r = c.post(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/api-keys",
           headers=H, json={"name": DEMO_KEY_NAME})
step("API key created", r.status_code == 201, str(r.status_code))
RAW_KEY = r.json()["key"]
KEY_ID  = r.json()["api_key"]["id"]
step("Key format valid", RAW_KEY.startswith("po_live_"), RAW_KEY[:12])
print(f"     key={RAW_KEY[:15]}...")
print(f"     key_id={KEY_ID[:8]}...")

# ── 5. Write .env ─────────────────────────────────────────────────────────────
banner("Step 5 — Write demo-service/.env")

def update_env(path: str, updates: dict) -> None:
    """Update specific keys in an .env file, preserving all other lines."""
    try:
        with open(path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    result = []
    updated = set()
    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            result.append(f"{key}={updates[key]}\n")
            updated.add(key)
        else:
            result.append(line)

    # Append any keys that weren't already in the file
    for key, val in updates.items():
        if key not in updated:
            result.append(f"{key}={val}\n")

    with open(path, "w") as f:
        f.writelines(result)

update_env(ENV_FILE, {
    "PULSEOPS_API_KEY":      RAW_KEY,
    "PULSEOPS_SERVICE_NAME": SERVICE_NAME,
    "PULSEOPS_INGESTION_URL": "http://localhost:8000/v1/telemetry",
})

step(".env written", os.path.exists(ENV_FILE), ENV_FILE)

# Verify it reads back correctly
with open(ENV_FILE) as f:
    content = f.read()
step("API key in .env", f"PULSEOPS_API_KEY={RAW_KEY}" in content)
step("Service name in .env", f"PULSEOPS_SERVICE_NAME={SERVICE_NAME}" in content)

# ── Summary ───────────────────────────────────────────────────────────────────
banner("Setup Complete")
print(f"  Organization : {orgs[0]['name']}")
print(f"  Project ID   : {PROJ_ID}")
print(f"  Service name : {SERVICE_NAME}")
print(f"  API Key      : {RAW_KEY[:15]}...")
print(f"  .env updated : {ENV_FILE}")
print(f"""
Next step — start the demo service:
  cd demo-service
  .\\venv\\Scripts\\Activate.ps1
  uvicorn app.main:app --reload --port 8001
""")

c.close()
