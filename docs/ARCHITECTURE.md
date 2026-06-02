# Architecture — Deal Scout LK

## Overview

Deal Scout LK is a **local-first, two-tier web application**. A Python FastAPI backend scrapes Sri Lankan bank websites with Playwright and serves offer data via REST. A React frontend consumes that API and renders three views: card grid, calendar, and bank comparison matrix.

There is no database. State is held in memory and periodically persisted to a single JSON cache file.

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (localhost:5173)                                    │
│  React + Vite dev server                                     │
│  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌─────────────┐  │
│  │  Header  │  │ Filters │  │ CardView │  │ CalendarView│  │
│  └──────────┘  └─────────┘  └──────────┘  └─────────────┘  │
│          ↕  useOffers hook  ↕  lib/api.js  ↕                │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP /api/*  (Vite proxy)
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI  (localhost:8000)                                   │
│  main.py                                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  In-memory offer list  │  Cache TTL logic            │   │
│  └──────────────┬───────────────────────────────────────┘   │
│                 │ asyncio.gather                             │
│  ┌──────────────▼───────────────────────────────────────┐   │
│  │  scraper.py — 8 async bank scrapers                  │   │
│  │  Playwright / headless Chromium                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                 │ .offers_cache.json                         │
└─────────────────┼───────────────────────────────────────────┘
                  ↕ file I/O
          backend/.offers_cache.json
```

## Backend

### `main.py` — FastAPI application

**Startup sequence:**
1. Load `backend/.offers_cache.json` if it exists.
2. If the cache is present and younger than 12 hours, populate the in-memory list and skip scraping.
3. If the cache is missing or stale, fire `_do_scrape()` as a background task.

**In-memory state** (module-level globals):

| Variable | Type | Purpose |
|---|---|---|
| `_offers` | `List[Dict]` | Serialised offer dicts currently served by the API |
| `_last_scraped` | `Optional[datetime]` | Timestamp of the last successful scrape |
| `_scraping_in_progress` | `bool` | Prevents concurrent scrape runs |
| `_scrape_errors` | `Dict[str, str]` | Per-bank error messages from the last run |

**Cache format** (`backend/.offers_cache.json`):
```json
{
  "scraped_at": "2025-06-01T14:32:00+05:30",
  "offers": [ { ...offer dict... }, ... ]
}
```

**Offer serialisation** — `_offer_to_dict()` in `main.py` converts an `Offer` dataclass to a dict and adds computed fields (`is_active_today`, `is_active_this_week`, `days_remaining`, `id`). The `id` is the first 12 hex chars of MD5(bank|supermarket|offer_text).

### `scraper.py` — Scraping engine and ICS builder

**`Offer` dataclass** is the canonical data shape. All scrapers return `List[Offer]`.

**`fetch_page(browser, url, ...)`** — shared Playwright helper:
- Creates a fresh browser context per call (isolated cookies/state).
- Injects a `navigator.webdriver = undefined` override to avoid bot detection.
- Waits for a CSS selector and an additional timeout before returning BeautifulSoup.

**Per-bank scrapers** — each is an `async def scrape_<key>(browser) -> List[Offer]`. They share common helpers:

| Helper | Purpose |
|---|---|
| `detect_supermarket(text)` | Keyword matching → canonical supermarket name |
| `extract_offer_text(text)` | Strips marketing noise, returns ≤120-char offer string |
| `parse_days(text)` | Returns `List[int]` weekday indices from free text |
| `parse_date(text)` / `parse_date_range(text)` | Regex date parser supporting multiple formats |
| `detect_card_type(text)` | Returns "Credit", "Debit", or "Credit / Debit" |

**`_generic_scrape()`** — fallback scraper that tries three HTML strategies (offer cards → heading+sibling → paragraph keywords). Used when a bank's layout is too variable for a dedicated scraper.

**`build_ics(offers) -> Calendar`** — converts `List[Offer]` to an `icalendar.Calendar`:
- If `days_of_week` is set, expands into one VEVENT per matching weekday occurrence.
- Otherwise creates a single all-day spanning event.
- Event UIDs are deterministic so re-imports do not create duplicates.

**`BANKS` registry** — dict mapping short key → `{name, fn}`. This is the single place to add or remove bank support.

### `manual_offers.py`

A plain Python file containing `MANUAL_OFFERS: list[Offer]`. Imported dynamically by `main.py` during every scrape run and by the CLI `scraper.py`. Edit this file to add offers when a bank blocks automated scraping.

## Frontend

### State management

All server state and filter state lives in the **`useOffers` hook** (`hooks/useOffers.js`). Components receive values and setters as props — there is no Context API or global store.

```
useOffers
  ├─ offers[]         fetched from /api/offers (filtered server-side)
  ├─ status           from /api/status
  ├─ banks[]          from /api/banks
  ├─ supermarkets[]   from /api/supermarkets
  ├─ selectedBanks, cardFilter, smFilter, activeToday, activeWeek  (filter state)
  └─ triggerScrape()  posts to /api/scrape, then polls /api/status until done
```

### Polling

While `status.scraping === true`, `useOffers` polls `/api/status` every 2.5 s. When scraping ends it fetches the offer list once more and clears the interval.

### API client (`lib/api.js`)

Thin `fetch` wrapper. All endpoint URLs, query-string construction, and ICS download logic live here. Components and hooks call `api.*` methods and never call `fetch()` directly.

### Component tree

```
App.jsx
├── Header.jsx          — title, scrape status, Refresh, Download .ics, Add to GCal
├── Filters.jsx         — bank chips, card type toggle, supermarket dropdown, timing filters
└── [view]
    ├── OfferCard.jsx   — single offer tile with bank colour badge
    ├── CalendarView.jsx — react-calendar with per-day offer sidebar
    └── BankCompare.jsx  — supermarket × bank matrix table
```

### Vite proxy

`vite.config.js` proxies `/api` to `http://localhost:8000`. This means the frontend can use relative `/api/...` URLs in development and the same paths will work when the backend is deployed behind the same origin.

## Data flow — on page load

```
Browser opens localhost:5173
  → useOffers mounts
  → GET /api/status            (is scraping? how old is cache?)
  → GET /api/offers            (current offer list, server-side filtered)
  → GET /api/banks
  → GET /api/supermarkets
  if status.scraping:
    → poll /api/status every 2.5 s
    → when done: GET /api/offers (refresh)
```

## Data flow — on Refresh button click

```
triggerScrape()
  → POST /api/scrape
  → backend: _do_scrape() fired as background task
  → GET /api/status  (confirm scraping=true)
  → poll /api/status every 2.5 s
  → when done: GET /api/offers
```

## ICS export data flow

```
User clicks Download .ics
  → api.downloadIcs(currentFilters)
  → GET /api/ics?banks=...&cards=...
  → backend rebuilds Offer objects from in-memory _offers
  → build_ics() generates Calendar
  → Response(content=cal.to_ical(), media_type="text/calendar")
  → browser triggers file download
```

## Timezone handling

All times are `Asia/Colombo` (UTC+5:30). Python uses `zoneinfo.ZoneInfo` (3.9+) with a `pytz` fallback for 3.8. The `is_active_today` and `is_active_this_week` checks in `main.py` use `date.today()` which is the server's local date — the server is assumed to run in the Sri Lanka timezone or a timezone-aware comparison is done using `TZ`.

## Scaling considerations (if ever deployed)

- The in-memory state and file cache are not suitable for multi-process deployments. Replace with a shared cache (Redis or a database) if running under Gunicorn workers.
- The CORS allowlist in `main.py` only permits `localhost`. Update it for any production domain.
- The Google Calendar "Add by URL" flow (`/api/google-calendar-url`) hardcodes `http://localhost:8000`. This must be updated to the public backend URL for Option 2 calendar sync to work.
