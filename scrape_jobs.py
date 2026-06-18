"""
Job Scraper - Scrapes Data Science / AI / ML jobs daily
and sends new listings via Email + Slack.
"""

import csv
import hashlib
import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from jobspy import scrape_jobs

# ── Config ────────────────────────────────────────────────────────────────────

SEARCH_CONFIGS = [
    {
        "search_term": "data scientist",
        "location": "United States",
        "hours_old": 24,
        "results_wanted": 15,
    },
    {
        "search_term": "machine learning engineer",
        "location": "United States",
        "hours_old": 24,
        "results_wanted": 15,
    },
    {
        "search_term": "AI engineer",
        "location": "United States",
        "hours_old": 24,
        "results_wanted": 10,
    },
    {
        "search_term": "MLOps engineer",
        "location": "United States",
        "hours_old": 24,
        "results_wanted": 10,
    },
]

SITES = ["indeed", "linkedin", "zip_recruiter", "google"]

SEEN_JOBS_FILE = Path("seen_jobs.json")

# ── Seen-jobs tracking ────────────────────────────────────────────────────────

def load_seen_jobs() -> set:
    if SEEN_JOBS_FILE.exists():
        with open(SEEN_JOBS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_jobs(seen: set):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)


def job_id(row) -> str:
    key = f"{row.get('title','')}-{row.get('company','')}-{row.get('location','')}"
    return hashlib.md5(key.encode()).hexdigest()


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_new_jobs(seen_ids: set) -> list[dict]:
    all_new = []

    for cfg in SEARCH_CONFIGS:
        print(f"  Scraping: {cfg['search_term']} ...")
        try:
            df = scrape_jobs(
                site_name=SITES,
                search_term=cfg["search_term"],
                google_search_term=(
                    f"{cfg['search_term']} jobs {cfg['location']} since yesterday"
                ),
                location=cfg["location"],
                hours_old=cfg["hours_old"],
                results_wanted=cfg["results_wanted"],
                country_indeed="USA",
                description_format="markdown",
                verbose=0,
            )
        except Exception as e:
            print(f"  ⚠ Error scraping {cfg['search_term']}: {e}")
            continue

        if df is None or df.empty:
            print(f"  No results for {cfg['search_term']}")
            continue

        for _, row in df.iterrows():
            jid = job_id(row)
            if jid not in seen_ids:
                seen_ids.add(jid)
                all_new.append({
                    "id": jid,
                    "title": row.get("title", "N/A"),
                    "company": row.get("company", "N/A"),
                    "location": row.get("location", "N/A"),
                    "job_type": row.get("job_type", ""),
                    "is_remote": row.get("is_remote", False),
                    "min_amount": row.get("min_amount", ""),
                    "max_amount": row.get("max_amount", ""),
                    "interval": row.get("interval", ""),
                    "job_url": row.get("job_url", ""),
                    "site": row.get("site", ""),
                    "date_posted": str(row.get("date_posted", "")),
                    "search_term": cfg["search_term"],
                })

    return all_new


# ── Email ─────────────────────────────────────────────────────────────────────

def salary_str(job: dict) -> str:
    lo = job.get("min_amount")
    hi = job.get("max_amount")
    interval = job.get("interval", "")
    if lo and hi:
        return f"${int(lo):,} – ${int(hi):,} / {interval}"
    if lo:
        return f"${int(lo):,}+ / {interval}"
    return "Not listed"


def build_email_html(jobs: list[dict]) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    remote_count = sum(1 for j in jobs if j.get("is_remote"))
    salaries = [j["max_amount"] for j in jobs if j.get("max_amount")]
    avg_max = int(sum(salaries) / len(salaries)) if salaries else 0

    # ── stat cards ────────────────────────────────────────────────
    stats_html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
      <tr>
        <td width="25%" style="padding-right:8px;">
          <div style="background:#f3f4f6;border-radius:10px;padding:14px 16px;text-align:center;">
            <div style="font-size:24px;font-weight:700;color:#111827;">{len(jobs)}</div>
            <div style="font-size:11px;color:#6b7280;margin-top:3px;">new jobs today</div>
          </div>
        </td>
        <td width="25%" style="padding-right:8px;">
          <div style="background:#f3f4f6;border-radius:10px;padding:14px 16px;text-align:center;">
            <div style="font-size:24px;font-weight:700;color:#111827;">{remote_count}</div>
            <div style="font-size:11px;color:#6b7280;margin-top:3px;">remote roles</div>
          </div>
        </td>
        <td width="25%" style="padding-right:8px;">
          <div style="background:#f3f4f6;border-radius:10px;padding:14px 16px;text-align:center;">
            <div style="font-size:24px;font-weight:700;color:#111827;">${avg_max:,}</div>
            <div style="font-size:11px;color:#6b7280;margin-top:3px;">avg max salary</div>
          </div>
        </td>
        <td width="25%">
          <div style="background:#f3f4f6;border-radius:10px;padding:14px 16px;text-align:center;">
            <div style="font-size:24px;font-weight:700;color:#111827;">4</div>
            <div style="font-size:11px;color:#6b7280;margin-top:3px;">sources scraped</div>
          </div>
        </td>
      </tr>
    </table>"""

    # ── job cards ─────────────────────────────────────────────────
    cards_html = ""
    source_colors = {
        "indeed": "#0F6E56", "linkedin": "#185FA5",
        "zip_recruiter": "#993C1D", "google": "#854F0B",
    }
    for j in jobs:
        sal = salary_str(j)
        remote_tag = (
            '<span style="background:#d1fae5;color:#065f46;font-size:11px;'
            'padding:3px 8px;border-radius:6px;border:1px solid #a7f3d0;margin-left:6px;">'
            '&#127968; Remote</span>'
            if j.get("is_remote") else ""
        )
        src = j.get("site", "")
        src_color = source_colors.get(src, "#888")
        src_label = src.replace("_", " ").title()
        cards_html += f"""
        <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;
                    padding:16px 18px;margin-bottom:10px;border-left:3px solid #7c3aed;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="vertical-align:top;">
                <a href="{j['job_url']}" style="font-size:15px;font-weight:600;
                   color:#111827;text-decoration:none;">{j['title']}</a>{remote_tag}
                <div style="color:#6b7280;font-size:13px;margin-top:4px;">{j['company']}</div>
                <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;">
                  <span style="font-size:11px;color:#6b7280;background:#f9fafb;
                               border:1px solid #e5e7eb;border-radius:6px;padding:3px 8px;">
                    &#128205; {j['location']}
                  </span>
                  <span style="font-size:11px;border-radius:6px;padding:3px 8px;
                               background:#f0f0f0;color:{src_color};border:1px solid #e5e7eb;">
                    &#9679; {src_label}
                  </span>
                  <span style="font-size:11px;color:#374151;background:#fafafa;
                               border:1px solid #e5e7eb;border-radius:6px;padding:3px 8px;">
                    &#128176; {sal}
                  </span>
                </div>
              </td>
              <td style="vertical-align:middle;text-align:right;padding-left:12px;white-space:nowrap;">
                <a href="{j['job_url']}" style="background:#7c3aed;color:#ffffff;
                   padding:8px 18px;border-radius:8px;text-decoration:none;
                   font-size:13px;font-weight:500;">Apply &rarr;</a>
              </td>
            </tr>
          </table>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:680px;margin:32px auto;padding:0 16px;">

  <!-- header -->
  <div style="background:#1e1b4b;border-radius:16px 16px 0 0;padding:28px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <div style="display:inline-block;background:rgba(255,255,255,.12);border-radius:10px;
                      padding:8px 10px;margin-bottom:12px;font-size:20px;">&#129302;</div>
          <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;line-height:1.2;">
            Daily AI/ML job digest
          </h1>
          <p style="margin:6px 0 0;color:#a5b4fc;font-size:13px;">
            {today} &nbsp;&#183;&nbsp; {len(jobs)} new listings across LinkedIn, Indeed, ZipRecruiter &amp; Google
          </p>
        </td>
      </tr>
    </table>
  </div>

  <!-- body -->
  <div style="background:#ffffff;border-radius:0 0 16px 16px;padding:24px 32px 28px;">
    {stats_html}
    <div style="font-size:11px;font-weight:600;color:#9ca3af;letter-spacing:.06em;
                text-transform:uppercase;margin-bottom:12px;">New listings</div>
    {cards_html}
    <div style="border-top:1px solid #f3f4f6;margin-top:20px;padding-top:16px;
                color:#9ca3af;font-size:11px;display:flex;justify-content:space-between;">
      <span>Powered by JobSpy &middot; runs daily at 8:00 AM UTC</span>
      <a href="https://github.com/speedyapply/JobSpy" style="color:#9ca3af;">GitHub</a>
    </div>
  </div>

</div>
</body></html>"""


def send_email(jobs: list[dict]):
    sender = os.environ["EMAIL_SENDER"]        # your Gmail address
    password = os.environ["EMAIL_APP_PASSWORD"] # Gmail App Password
    recipient = os.environ["EMAIL_RECIPIENT"]  # where to send

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 {len(jobs)} New AI/ML Jobs — {datetime.now().strftime('%b %d')}"
    msg["From"] = sender
    msg["To"] = recipient

    msg.attach(MIMEText(build_email_html(jobs), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.sendmail(sender, recipient, msg.as_string())
    print(f"  ✅ Email sent to {recipient}")


# ── Slack ─────────────────────────────────────────────────────────────────────

def send_slack(jobs: list[dict]):
    webhook = os.environ["SLACK_WEBHOOK_URL"]
    today = datetime.now().strftime("%B %d, %Y")
    remote_count = sum(1 for j in jobs if j.get("is_remote"))
    salaries = [j["max_amount"] for j in jobs if j.get("max_amount")]
    avg_max = int(sum(salaries) / len(salaries)) if salaries else 0

    source_emoji = {
        "indeed": ":green_circle:", "linkedin": ":large_blue_circle:",
        "zip_recruiter": ":large_orange_circle:", "google": ":yellow_circle:",
    }

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":robot_face: *Daily AI/ML job digest* — {today}\n"
                    f"> *{len(jobs)} new listings* scraped across LinkedIn, Indeed, ZipRecruiter & Google"
                ),
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f":briefcase: *{len(jobs)}*\nNew jobs today"},
                {"type": "mrkdwn", "text": f":house: *{remote_count}*\nRemote roles"},
                {"type": "mrkdwn", "text": f":moneybag: *${avg_max:,}*\nAvg max salary"},
                {"type": "mrkdwn", "text": f":satellite: *4*\nSources scraped"},
            ],
        },
        {"type": "divider"},
    ]

    for j in jobs[:20]:
        src = j.get("site", "")
        src_dot = source_emoji.get(src, ":white_circle:")
        remote_tag = " :house: `remote`" if j.get("is_remote") else ""
        sal = salary_str(j)
        sal_text = f"\n:money_with_wings: {sal}" if sal != "Not listed" else ""

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*<{j['job_url']}|{j['title']}>*{remote_tag}\n"
                    f":office: {j['company']}   :round_pushpin: {j['location']}"
                    f"{sal_text}\n"
                    f"{src_dot} {src.replace('_',' ').title()}"
                ),
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Apply →", "emoji": True},
                "style": "primary",
                "url": j["job_url"],
                "action_id": f"apply_{j['id'][:8]}",
            },
        })
        blocks.append({"type": "divider"})

    if len(jobs) > 20:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_...and {len(jobs)-20} more jobs in today's run._"},
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": ":clock3: Runs daily at 8:00 AM UTC · Powered by JobSpy"},
        ],
    })

    resp = requests.post(webhook, json={"blocks": blocks}, timeout=15)
    resp.raise_for_status()
    print(f"  ✅ Slack notification sent ({len(jobs)} jobs)")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print(f"  Job Scraper  ·  {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*55}\n")

    seen = load_seen_jobs()
    print(f"Previously seen jobs: {len(seen)}\n")

    new_jobs = fetch_new_jobs(seen)
    save_seen_jobs(seen)

    print(f"\nNew jobs found: {len(new_jobs)}\n")

    if not new_jobs:
        print("Nothing new today — skipping notifications.")
        return

    # Save to CSV for the repo artifact
    with open("jobs_latest.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(new_jobs[0].keys()))
        writer.writeheader()
        writer.writerows(new_jobs)
    with open("jobs_latest.json", "w") as jf:
        import json as _json
        _json.dump(new_jobs, jf, ensure_ascii=False, default=str)
    print(f"  📄 Saved jobs_latest.csv + jobs_latest.json")

    errors = []

    if os.environ.get("EMAIL_SENDER"):
        try:
            send_email(new_jobs)
        except Exception as e:
            errors.append(f"Email error: {e}")
            print(f"  ❌ {errors[-1]}")

    if os.environ.get("SLACK_WEBHOOK_URL"):
        try:
            send_slack(new_jobs)
        except Exception as e:
            errors.append(f"Slack error: {e}")
            print(f"  ❌ {errors[-1]}")

    if errors:
        sys.exit(1)

    print("\nDone! ✅")


if __name__ == "__main__":
    main()
