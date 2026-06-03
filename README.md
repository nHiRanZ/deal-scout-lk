# 🛒 LK Deals

**Sri Lanka Bank Supermarket Offers → Calendar**

Scrapes supermarket offers from 8 major Sri Lankan banks every day and shows
them in a card grid, calendar view, and comparison table. Exports to `.ics` for
Google Calendar or directly adds via URL.

**Live:** [nimila.online/deal-scout-lk](https://nimila.online/deal-scout-lk/) |
**Backend API:** [deal-scout-lk.onrender.com](https://deal-scout-lk.onrender.com/api/status)

---

## Quick Start (local)

```bash
# 1. Install Python dependencies (once)
cd backend
pip install -r requirements.txt
playwright install chromium

# 2. Install Node dependencies (once)
cd ../frontend
npm install

# 3. Start everything (from project root)
bash start.sh
```

Then open **http://localhost:5173**

---

## Project Structure

```
deal-scout-lk/
├── .github/workflows/
│   └── deploy.yml         ← GitHub Actions: builds & deploys frontend to Pages
├── backend/
│   ├── main.py            ← FastAPI server, cache, scheduler, REST API
│   ├── scraper.py         ← Playwright scrapers for all 8 banks + ICS builder
│   ├── manual_offers.py   ← Hand-enter offers when scraping fails
│   ├── Dockerfile         ← Container definition for Render deployment
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx        ← Layout, view switcher
│       ├── components/
│       │   ├── Header     ← Status, theme toggle, Download/Add to GCal
│       │   ├── Filters    ← Bank, card type, supermarket, timing filters
│       │   ├── OfferCard  ← Individual offer card
│       │   ├── CalendarView ← Mini calendar with per-day offer list
│       │   └── BankCompare  ← Matrix table (supermarket × bank)
│       └── hooks/
│           ├── useOffers.js ← Data fetching, filter state, polling
│           └── useTheme.js  ← Light/dark theme with localStorage persistence
└── start.sh               ← One-command local launcher
```

---

## Features

| Feature | Details |
|---|---|
| **Scheduled scraping** | Runs at 06:00, 10:00, 14:00, 18:00, 22:00 Asia/Colombo |
| **12h cache** | Saves to `.offers_cache.json`; skips re-scrape if cache is fresh |
| **Card view** | Filterable grid of all offers with bank colour coding |
| **Calendar view** | Click any date to see active offers for that day |
| **Compare view** | Supermarket × Bank matrix — spot the best deal at a glance |
| **Light / dark theme** | Toggle in the header; preference saved to localStorage |
| **Download .ics** | Exports filtered offers as a calendar file |
| **Add to Google Calendar** | Opens Google's "Add calendar by URL" page |
| **Manual sync** | `GET /api/scrape?key=<SCRAPE_KEY>` triggers an immediate scrape |

---

## Banks Supported

| Key | Bank |
|---|---|
| `sampath` | Sampath Bank |
| `seylan` | Seylan Bank |
| `combank` | Commercial Bank |
| `ntb` | Nations Trust Bank |
| `hnb` | Hatton National Bank |
| `boc` | Bank of Ceylon |
| `dfcc` | DFCC Bank |
| `peoples` | People's Bank |

---

## Deployment

### Backend — Render.com

The backend runs as a Docker web service on Render's free tier.

#### First-time setup

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New → Web Service**.
3. Connect the repo and set:
   - **Root Directory**: `backend`
   - **Runtime**: Docker
   - **Instance Type**: Free
4. Add environment variables:
   | Variable | Value |
   |---|---|
   | `PORT` | `8000` |
   | `PYTHONUNBUFFERED` | `1` |
   | `SCRAPE_KEY` | any secret string (used to protect the manual sync endpoint) |
5. Click **Deploy**.

#### Keep-alive (free tier)

Render's free tier sleeps after 15 min of inactivity, which would prevent the
scheduled scraper from running. Set up a free UptimeRobot monitor:

1. Create a free account at [uptimerobot.com](https://uptimerobot.com).
2. **New Monitor → HTTP(S)** → URL: `https://<your-service>.onrender.com/api/status`
3. Interval: **5 minutes**.

#### Manual scrape trigger

```
GET https://<your-service>.onrender.com/api/scrape?key=<SCRAPE_KEY>
```

Returns `{"status": "started"}` or `{"status": "already_running"}`.

#### Redeployment

Render auto-deploys on every push to `main`. To force a redeploy, push any
change or use the Render dashboard → **Manual Deploy**.

---

### Frontend — GitHub Pages

The frontend is a Vite + React SPA deployed to GitHub Pages via the
`.github/workflows/deploy.yml` workflow.

#### First-time setup

1. Go to **github.com/\<owner\>/deal-scout-lk → Settings → Pages**.
2. Under **Source**, select **"GitHub Actions"** and save.
3. The `deploy.yml` workflow will now run on every push to `main`.

That's it — no secrets or environment variables needed in the repo. The
`VITE_API_BASE` pointing to the Render backend URL is baked into the workflow.

#### Update the backend URL

If the Render service URL changes, update this line in `.github/workflows/deploy.yml`:

```yaml
VITE_API_BASE: https://deal-scout-lk.onrender.com/api
```

#### Manual redeploy

Go to **Actions → "Deploy Frontend to GitHub Pages" → Run workflow**.

#### Local dev vs production

| Context | API base |
|---|---|
| `npm run dev` (local) | `/api` → proxied to `localhost:8000` by Vite |
| Production build | `VITE_API_BASE` env var set by the GitHub Actions workflow |

---

## Manual Offers

When a bank site blocks scraping, open `backend/manual_offers.py` and add the offer:

```python
Offer(
    bank="Sampath Bank",
    supermarket="Keells",
    offer_text="25% off total bill",
    card_type="Credit",
    valid_from=date(2025, 6, 1),
    valid_to=date(2025, 6, 30),
    days_of_week=[0],          # 0=Mon … 6=Sun
    source_url="https://www.sampath.lk/...",
)
```

Push the change — Render will auto-deploy and the new offers will appear on the
next scrape cycle. To pick them up immediately, trigger a manual scrape via the
`/api/scrape` endpoint.

---

## Google Calendar Integration

**Option 1 — Download & Import (always works)**
1. Click **Download .ics** in the header
2. Open the file → Google Calendar prompts to import

**Option 2 — Add by URL (requires a publicly accessible backend)**
1. Click **Add to Google Cal** in the header
2. Google Calendar opens with the URL pre-filled
3. Click **Add Calendar**
