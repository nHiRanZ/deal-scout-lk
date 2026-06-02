# Requirements — Deal Scout LK

## Problem statement

Sri Lankan supermarket shoppers must check 8 different bank websites individually to find which credit or debit cards give discounts at which supermarkets on which days. Deal Scout LK aggregates all offers into one place and lets users filter, browse by calendar, and export to Google Calendar.

## Supported banks

| Key | Bank name |
|---|---|
| `sampath` | Sampath Bank |
| `seylan` | Seylan Bank |
| `combank` | Commercial Bank of Ceylon |
| `ntb` | Nations Trust Bank |
| `hnb` | Hatton National Bank |
| `boc` | Bank of Ceylon |
| `dfcc` | DFCC Bank |
| `peoples` | People's Bank |

## Supported supermarkets

| Name | Known keywords |
|---|---|
| Keells | keells, keell's super |
| Cargills Food City | cargills, food city, cargill's |
| Laugfs | laugfs, laughs super |
| Arpico Super Centre | arpico |
| Spar | spar |
| Glomark | glomark |

## Functional requirements

### Data collection

- **FR-01** The system must scrape offer data from all 8 supported banks automatically at startup if the cache is older than 12 hours or absent.
- **FR-02** All 8 bank scrapers must run concurrently; one scraper failing must not block others.
- **FR-03** Per-bank scraping errors must be surfaced to the UI (shown in the status bar or error state).
- **FR-04** The system must support manually curated offers via `backend/manual_offers.py`; these must be merged with scraped data on every scrape run.
- **FR-05** Scraped data must be cached locally in `backend/.offers_cache.json` with a 12-hour TTL.

### Offer model

- **FR-06** Each offer must capture: bank, supermarket, offer text, card type (Credit / Debit / both), validity dates (from/to), applicable days of week, and source URL.
- **FR-07** An offer with no `valid_to` date must be treated as active for 90 days from today.
- **FR-08** An offer with `days_of_week = []` must be treated as active every day within its validity window.

### API

- **FR-09** The backend must expose a REST API that the frontend can filter by: bank key(s), card type, supermarket name (substring), active-today flag, active-this-week flag.
- **FR-10** The backend must expose a `/api/status` endpoint returning scrape state, cache age, offer count, and per-bank error map.
- **FR-11** A POST to `/api/scrape` must trigger a background re-scrape without blocking the response.
- **FR-12** The backend must produce a valid RFC 5545 ICS calendar file at `/api/ics`, filterable by the same parameters as `/api/offers`.

### Frontend — Card view

- **FR-13** Offers must be displayed as a responsive grid of cards showing: bank name (with colour badge), supermarket, offer text, card type, validity dates, and applicable days.
- **FR-14** Users must be able to filter by: one or more banks, card type (credit / debit / both), supermarket, and timing (active today / active this week).
- **FR-15** The UI must poll the backend while a scrape is in progress and refresh the offer list automatically when it completes.

### Frontend — Calendar view

- **FR-16** A calendar must show the current month with per-day offer counts.
- **FR-17** Clicking a date must show the list of offers active on that day.

### Frontend — Compare view

- **FR-18** A matrix table must show supermarkets as rows and banks as columns, with offer text at each intersection.
- **FR-19** Banks with no offer for a given supermarket must show an empty / dash cell.

### Export

- **FR-20** Users must be able to download a `.ics` file containing offers filtered by the current bank and card-type selection.
- **FR-21** Each day-of-week offer (e.g. "every Monday") must be expanded into individual calendar events per occurrence within the validity window.
- **FR-22** ICS event UIDs must be deterministic so re-importing does not create duplicate events.
- **FR-23** Users must be able to open the Google Calendar "Add by URL" flow from the UI (requires a publicly accessible backend URL; falls back gracefully when running locally).

## Non-functional requirements

### Performance

- **NFR-01** The full scrape of all 8 banks must complete in under 3 minutes on a standard broadband connection (banks run concurrently; individual page load ≤ 40 s timeout).
- **NFR-02** API responses for cached data must be served in under 200 ms.
- **NFR-03** The frontend must remain responsive while a scrape is running (non-blocking background task).

### Reliability

- **NFR-04** A scraper failure for one bank must not prevent offers from other banks from being served.
- **NFR-05** If the cache file is corrupted, the system must log a warning and trigger a fresh scrape rather than crashing.

### Compatibility

- **NFR-06** The backend must run on Python 3.8 or higher.
- **NFR-07** The frontend must run in any modern Chromium/Firefox/Safari browser.
- **NFR-08** The `.ics` output must be importable into Google Calendar, Apple Calendar, and Outlook.

### Security (local use)

- **NFR-09** CORS is restricted to `localhost:5173` and `localhost:3000` by default; no public endpoints are exposed.
- **NFR-10** No user data is collected or persisted beyond the offer cache.

### Maintainability

- **NFR-11** Adding a new bank scraper must require changes to exactly two files: `scraper.py` (scraper + registry) and `SCRAPING_NOTES.md`.
- **NFR-12** When a bank blocks scraping, manual offers must be addable without code changes to any file other than `manual_offers.py`.

## Out of scope

- User accounts or authentication.
- Price comparison (offers are percentage discounts, not absolute prices).
- Push notifications.
- Mobile native app.
- Multi-user / server deployment (the app is designed to run locally).
- Historical offer tracking or archiving.
