# 🛒 LK Deals

**Sri Lanka Bank Supermarket Offers → Calendar**

Scrapes supermarket offers from 8 major Sri Lankan banks every day and shows
them in a card grid, calendar view, and comparison table. Exports to `.ics` for
Google Calendar or directly adds via URL.

---

## Quick Start

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
lk-deals/
├── backend/
│   ├── main.py            ← FastAPI server + caching
│   ├── scraper.py         ← Playwright scraper for all 8 banks
│   ├── manual_offers.py   ← Hand-enter offers when scraping fails
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx        ← Layout, view switcher
│       ├── components/
│       │   ├── Header     ← Status, Refresh, Download/Add to GCal
│       │   ├── Filters    ← Bank, card type, supermarket, timing filters
│       │   ├── OfferCard  ← Individual offer card
│       │   ├── CalendarView ← Mini calendar with per-day offer list
│       │   └── BankCompare  ← Matrix table (supermarket × bank)
│       └── hooks/
│           └── useOffers  ← Data fetching, filter state, polling
└── start.sh               ← One-command launch
```

---

## Features

| Feature | Details |
|---|---|
| **Auto-scrape on startup** | Runs when you open the app; re-scrapes if cache > 12h old |
| **Manual refresh** | "Refresh" button in the header |
| **12h cache** | Saves to `.offers_cache.json`; won't hit bank sites again until stale |
| **Card view** | Filterable grid of all offers with bank colour coding |
| **Calendar view** | Click any date to see active offers for that day |
| **Compare view** | Supermarket × Bank matrix — spot the best deal at a glance |
| **Download .ics** | Exports filtered offers as a calendar file |
| **Add to Google Calendar** | Opens Google's "Add calendar by URL" page |
| **Day-of-week expansion** | "Every Monday" → individual events per occurrence in ICS |

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

Hit **Refresh** in the UI to pick it up.

---

## Google Calendar Integration

**Option 1 — Download & Import (always works locally)**
1. Click **Download .ics** in the header
2. Open the file → Google Calendar prompts to import

**Option 2 — Add by URL (requires the server to be publicly accessible)**
1. Click **Add to Google Cal** in the header
2. Google Calendar opens with the URL pre-filled
3. Click **Add Calendar**

> For local-only use, Option 1 is the reliable choice.
> To use Option 2 permanently, deploy the backend and update the URL in `api.js`.
