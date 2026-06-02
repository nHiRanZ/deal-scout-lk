# CLAUDE.md — Deal Scout LK

## What this project is

A local web app that scrapes supermarket credit/debit card offers from 8 Sri Lankan bank websites daily and presents them as a filterable card grid, calendar view, and comparison matrix. Users can export offers as `.ics` to import into Google Calendar.

## Repository layout

```
deal-scout-lk/
├── backend/
│   ├── main.py            ← FastAPI server, cache logic, REST API
│   ├── scraper.py         ← Playwright scrapers + ICS builder + Offer dataclass
│   ├── manual_offers.py   ← Hand-curated offers when scraping is blocked
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx        ← View switcher (cards / calendar / compare)
│       ├── lib/api.js     ← Thin fetch wrapper for the backend REST API
│       ├── hooks/useOffers.js  ← All data-fetch + filter state
│       └── components/
│           ├── Header.jsx
│           ├── Filters.jsx
│           ├── OfferCard.jsx
│           ├── CalendarView.jsx
│           └── BankCompare.jsx
├── docs/
│   ├── ARCHITECTURE.md
│   └── REQUIREMENTS.md
├── SCRAPING_NOTES.md      ← Bank-specific scraping tips and known failures
├── start.sh               ← One-command launcher
└── .gitignore
```

## How to run

```bash
# From project root — starts both servers and opens the browser
bash start.sh
```

Or manually:

```bash
# Backend (http://localhost:8000)
cd backend && python main.py

# Frontend (http://localhost:5173)
cd frontend && npm run dev
```

Vite proxies `/api/*` to `localhost:8000` — do not hard-code the backend port in frontend JS.

## Key architectural facts

- **Single `Offer` dataclass** in `scraper.py` is the canonical data shape shared by scrapers, the ICS builder, `manual_offers.py`, and the serialisation logic in `main.py`.
- **Cache** is a flat JSON file at `backend/.offers_cache.json`. It is gitignored. TTL = 12 h.
- **Scraping is async** — all 8 banks run concurrently via `asyncio.gather` inside a single headless Chromium instance. Never make bank scrapers synchronous.
- **`BANKS` dict** in `scraper.py` is the registry; adding a new bank means adding an async scrape function and an entry there.
- **ICS UID** is deterministic (MD5 of bank|supermarket|offer_text|date) — re-importing does not create duplicates.
- **Frontend API** lives entirely in `frontend/src/lib/api.js`. Keep all `fetch()` calls there.
- **CSS Modules** — every component has a paired `.module.css`; do not add global styles or Tailwind.

## Coding conventions

- Python 3.8-compatible (uses `from __future__ import annotations`; `zoneinfo` with `pytz` fallback).
- No type: ignore, no bare `except` without a log.
- Frontend: plain React (no Redux, no context providers). State lives in `useOffers`.
- No test suite exists yet. Do not add placeholder test files unless asked.

## What NOT to do

- Do not modify `.offers_cache.json` directly — delete it to force a re-scrape.
- Do not change the CORS origins in `main.py` unless the user changes the dev port.
- Do not install Tailwind or any CSS framework — the project uses CSS Modules.
- Do not add a build step to `start.sh`; it intentionally runs Vite in dev mode.
- Do not commit `.env` files or the cache file.

## Adding a new bank

1. Write `async def scrape_<key>(browser: Browser) -> List[Offer]` in `scraper.py`.
2. Register it in the `BANKS` dict at the bottom of `scraper.py`.
3. Add a color entry in `frontend/src/components/Header.module.css` (or wherever bank colors live).
4. Document the bank's URL and any known fragility in `SCRAPING_NOTES.md`.

## Scraping failures

When a bank site blocks scraping or changes its HTML:
1. Check `SCRAPING_NOTES.md` for known workarounds.
2. Add/update entries in `backend/manual_offers.py`.
3. Hit **Refresh** in the UI to reload.
