# ⚡ JobPulse — AI Job Intelligence Dashboard

Premium self-hosted job tracker for AI/ML roles. Scrapes 4 boards every 30 min, deploys to GitHub Pages (free), built-in AI chatbot via Groq (free, no card).

## Setup (15 min)

### 1 — Push to GitHub
```bash
git init && git add . && git commit -m "init"
git remote add origin https://github.com/YOUR_USERNAME/job-spy-alerts.git
git push -u origin main
```

### 2 — Enable GitHub Pages
Settings → Pages → Source: `gh-pages` branch → Save

Your live dashboard: `https://YOUR_USERNAME.github.io/job-spy-alerts/`

### 3 — Free Groq key (AI chatbot)
1. Go to console.groq.com → sign up (free, no card)
2. API Keys → Create → copy it
3. Paste into the dashboard on first load

Free tier: 14,400 req/day · Llama 3 · No card ever.

### 4 — GitHub Secrets
Settings → Secrets → Actions → New secret:

| Secret | Value |
|---|---|
| EMAIL_SENDER | your Gmail |
| EMAIL_APP_PASSWORD | Gmail App Password |
| EMAIL_RECIPIENT | where to send alerts |
| SLACK_WEBHOOK_URL | Slack Incoming Webhook URL |

### 5 — Test it
Actions tab → "Job Scraper — every 30 minutes" → Run workflow

## How it works
Every 30 min: scrapes LinkedIn/Indeed/ZipRecruiter/Google → deduplicates → emails + Slacks new jobs → injects data into dashboard → deploys to GitHub Pages. All free.

## Files
```
scripts/scrape_jobs.py     scraper + email + Slack
scripts/inject_jobs.py     patches dashboard with fresh data
jobpulse/index.html        dashboard source
docs/index.html            GitHub Pages output (auto-generated)
seen_jobs.json             dedup tracker
jobs_latest.json           last run data
```
