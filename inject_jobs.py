"""
inject_jobs.py
Reads jobs_latest.json (output of scrape_jobs.py) and injects
the job data into the dashboard HTML, then writes to docs/index.html
so GitHub Pages serves a live, data-fresh dashboard.
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime

DOCS = Path("docs")
DOCS.mkdir(exist_ok=True)

SRC_HTML  = Path("jobpulse/index.html")
DEST_HTML = DOCS / "index.html"
JOBS_JSON = Path("jobs_latest.json")

# ── Load jobs ─────────────────────────────────────────────────────────────────

ICON_MAP = {
    "data scientist":    "📊",
    "machine learning":  "🤖",
    "ml engineer":       "🤖",
    "ai engineer":       "✦",
    "nlp":               "🦙",
    "mlops":             "⚙️",
    "deep learning":     "🧠",
    "research":          "🔬",
}

BG_MAP = {
    "indeed":        "#0d1f18",
    "linkedin":      "#0d1625",
    "zip_recruiter": "#1f150d",
    "google":        "#1a1219",
}

def guess_type(title: str) -> str:
    t = title.lower()
    if "mlops" in t or "platform" in t or "infra" in t: return "mlops"
    if "ml engineer" in t or "machine learning engineer" in t: return "ml engineer"
    if "ai engineer" in t or "ai/ml" in t: return "ai engineer"
    if "data scientist" in t or "data science" in t: return "data scientist"
    if "research" in t: return "ai engineer"
    return "data scientist"

def guess_icon(title: str) -> str:
    t = title.lower()
    for kw, icon in ICON_MAP.items():
        if kw in t:
            return icon
    return "💼"

if JOBS_JSON.exists():
    with open(JOBS_JSON) as f:
        raw = json.load(f)
    jobs = []
    for r in raw:
        jobs.append({
            "title":      r.get("title", ""),
            "company":    r.get("company", ""),
            "location":   r.get("location", ""),
            "is_remote":  bool(r.get("is_remote", False)),
            "type":       guess_type(r.get("title", "")),
            "site":       r.get("site", ""),
            "min_amount": r.get("min_amount") or 0,
            "max_amount": r.get("max_amount") or 0,
            "job_url":    r.get("job_url", "#"),
            "date_posted": str(r.get("date_posted", datetime.now().date())),
            "icon":       guess_icon(r.get("title", "")),
            "bg":         BG_MAP.get(r.get("site", ""), "#1a1a25"),
        })
else:
    jobs = []
    print("  ⚠ jobs_latest.json not found — dashboard will show demo data")

jobs_js = json.dumps(jobs, ensure_ascii=False)

# ── Read & patch HTML ────────────────────────────────────────────────────────

html = SRC_HTML.read_text(encoding="utf-8")

# Replace the DEMO_JOBS constant with real scraped data
old_marker = "const DEMO_JOBS = ["
new_block   = f"const DEMO_JOBS = {jobs_js};\nconst _INJECTED_AT = '{datetime.utcnow().isoformat()}Z';\nconst _orig = ["
html = html.replace(old_marker, new_block, 1)

# Inject last-updated meta tag
html = html.replace(
    "</head>",
    f'<meta name="jobpulse-updated" content="{datetime.utcnow().isoformat()}Z">\n</head>',
    1,
)

DEST_HTML.write_text(html, encoding="utf-8")
print(f"  ✅ Dashboard written to {DEST_HTML} ({len(jobs)} jobs injected)")
