# AGENTS.md — Deal Scout LK

Agent instructions for any AI coding assistant working in this repository.

## Project summary

**Deal Scout LK** is a local-first web app that scrapes Sri Lankan bank websites for supermarket card offers and presents them in a React UI. Backend: FastAPI + Playwright. Frontend: React + Vite. No database — state lives in a JSON cache file.

## Environment setup

```bash
# Python (3.8+)
cd backend
pip install -r requirements.txt
playwright install chromium

# Node (18+)
cd frontend
npm install

# Run both servers
bash start.sh        # from project root
```

Servers: backend → `http://localhost:8000`, frontend → `http://localhost:5173`

## Repository map

| Path | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, cache management, REST endpoints |
| `backend/scraper.py` | Playwright scrapers, `Offer` dataclass, ICS builder, `BANKS` registry |
| `backend/manual_offers.py` | Hand-curated offers; auto-loaded on every scrape |
| `backend/requirements.txt` | Python dependencies |
| `frontend/src/lib/api.js` | All frontend→backend HTTP calls |
| `frontend/src/hooks/useOffers.js` | Filter state + data fetching |
| `frontend/src/components/` | React components (each paired with `.module.css`) |
| `SCRAPING_NOTES.md` | Per-bank scraping quirks and failure history |
| `docs/ARCHITECTURE.md` | Full system architecture |
| `docs/REQUIREMENTS.md` | Functional and non-functional requirements |

## Core data contract

`Offer` (defined in `scraper.py`) is the single source of truth for offer shape:

```python
@dataclass
class Offer:
    bank: str            # e.g. "Sampath Bank"
    supermarket: str     # e.g. "Keells"
    offer_text: str      # e.g. "30% off total bill"
    card_type: str       # "Credit" | "Debit" | "Credit / Debit"
    valid_from: Optional[date]
    valid_to: Optional[date]
    days_of_week: List[int]   # 0=Mon … 6=Sun, empty = all days in window
    source_url: str
    raw_terms: str
```

When serialised to JSON by `main.py`, the dict gains: `id`, `bank_key`, `is_active_today`, `is_active_this_week`, `days_remaining`.

## REST API (backend)

| Method | Path | Description |
|---|---|---|
| GET | `/api/status` | Scrape status, cache age, error map |
| POST | `/api/scrape?banks=...` | Trigger background scrape |
| GET | `/api/offers` | Filtered offer list |
| GET | `/api/banks` | List of supported banks |
| GET | `/api/supermarkets` | Supermarkets seen in current cache |
| GET | `/api/ics` | Download filtered ICS calendar file |
| GET | `/api/google-calendar-url` | Returns Google Calendar add-by-URL link |

Query params for `/api/offers` and `/api/ics`: `banks` (CSV of keys), `cards` (credit|debit|both), `supermarket`, `active_today`, `active_week`.

## Important invariants

1. **Scraping is always async** — `asyncio.gather` runs all bank scrapers concurrently. Do not make scraper functions synchronous.
2. **Single Chromium instance per scrape run** — scrapers receive a `Browser` object, not a `Playwright` instance.
3. **Cache file is write-only from code** — delete `backend/.offers_cache.json` to force a fresh scrape; never edit it directly.
4. **ICS UIDs are deterministic** — computed as MD5(bank|supermarket|offer_text|date). This prevents duplicates on re-import.
5. **All frontend HTTP calls go through `frontend/src/lib/api.js`** — do not call `fetch()` directly in components or hooks.
6. **CSS Modules only** — each component has its own `.module.css`. Do not introduce global CSS classes or CSS frameworks.

## Adding a new bank scraper

1. Implement `async def scrape_<key>(browser: Browser) -> List[Offer]` in `scraper.py`.
2. Add `"<key>": {"name": "Bank Display Name", "fn": scrape_<key>}` to the `BANKS` dict.
3. Add notes about the bank's page structure and any known fragility to `SCRAPING_NOTES.md`.

## Modifying manual offers

Edit `backend/manual_offers.py` and add an `Offer(...)` entry to `MANUAL_OFFERS`. The scraper loads this file automatically on every scrape. Useful when a bank blocks automated scraping.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| 0 offers for a bank | Bank changed HTML structure | Update the scraper function; add to `SCRAPING_NOTES.md` |
| Scraping hangs | Playwright timeout | Increase `extra_wait` in `fetch_page()` call for that bank |
| `is_active_today` all false | Cache from a different timezone | Delete cache file and re-scrape |
| Frontend shows stale data | Cache within TTL | Hit Refresh in the UI or delete the cache file |

## Constraints

- Python 3.8 minimum (`from __future__ import annotations` is intentional; `zoneinfo` has a `pytz` fallback).
- No test suite — do not add empty test scaffolding.
- Do not modify `start.sh` to run `vite build`; it is intentionally a dev-mode launcher.
- Do not change CORS origins in `main.py` without user instruction.
