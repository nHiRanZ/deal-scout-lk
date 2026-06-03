from __future__ import annotations
"""
LK Deals – FastAPI Backend
Scrapes Sri Lankan bank supermarket offers and serves them to the React frontend.
"""

import asyncio
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo

from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

# ── Scraper import ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from scraper import (
    Offer, build_ics, BANKS,
)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("lk-deals")

TZ = ZoneInfo("Asia/Colombo")
CACHE_FILE = Path(__file__).parent / ".offers_cache.json"
CACHE_TTL_HOURS = 12

# Scheduled scrape slots (hour of day, Asia/Colombo).
# Skips midnight-05:00 maintenance window; first run of day is 06:00.
SCRAPE_HOURS = [6, 10, 14, 18, 22]

app = FastAPI(title="LK Bank Deals API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://nimila.online",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory state ──────────────────────────────────────────────────────────
_offers: List[Dict] = []
_last_scraped: Optional[datetime] = None
_scraping_in_progress: bool = False
_scrape_errors: Dict[str, str] = {}


# ── Pydantic models ──────────────────────────────────────────────────────────
class OfferOut(BaseModel):
    id: str
    bank: str
    bank_key: str
    supermarket: str
    offer_text: str
    card_type: str
    valid_from: Optional[str]
    valid_to: Optional[str]
    days_of_week: List[int]
    source_url: str
    is_active_today: bool
    is_active_this_week: bool
    days_remaining: Optional[int]


class ScrapeStatus(BaseModel):
    last_scraped: Optional[str]
    offer_count: int
    scraping: bool
    errors: Dict[str, str]
    cache_age_minutes: Optional[int]


# ── Cache helpers ────────────────────────────────────────────────────────────
def _save_cache(offers: List[Dict]) -> None:
    CACHE_FILE.write_text(json.dumps({
        "scraped_at": datetime.now(TZ).isoformat(),
        "offers": offers,
    }, default=str))


def _load_cache() -> Tuple[List[Dict], Optional[datetime]]:
    if not CACHE_FILE.exists():
        return [], None
    try:
        data = json.loads(CACHE_FILE.read_text())
        scraped_at = datetime.fromisoformat(data["scraped_at"])
        return data["offers"], scraped_at
    except Exception:
        return [], None


def _offer_to_dict(offer: Offer, bank_key: str) -> Dict:
    today = date.today()

    def is_active_today(o: Offer) -> bool:
        start = o.valid_from or today
        end = o.valid_to or (today + timedelta(days=90))
        if not (start <= today <= end):
            return False
        if o.days_of_week:
            return today.weekday() in o.days_of_week
        return True

    def is_active_this_week(o: Offer) -> bool:
        start = o.valid_from or today
        end = o.valid_to or (today + timedelta(days=90))
        week_end = today + timedelta(days=6)
        if max(start, today) > min(end, week_end):
            return False
        if o.days_of_week:
            for i in range(7):
                d = today + timedelta(days=i)
                if d <= week_end and d.weekday() in o.days_of_week and start <= d <= end:
                    return True
            return False
        return True

    days_remaining = None
    if offer.valid_to:
        days_remaining = max(0, (offer.valid_to - today).days)

    import hashlib
    uid = hashlib.md5(
        "{}|{}|{}".format(offer.bank, offer.supermarket, offer.offer_text).encode()
    ).hexdigest()[:12]

    return {
        "id": uid,
        "bank": offer.bank,
        "bank_key": bank_key,
        "supermarket": offer.supermarket,
        "offer_text": offer.offer_text,
        "card_type": offer.card_type,
        "valid_from": offer.valid_from.isoformat() if offer.valid_from else None,
        "valid_to": offer.valid_to.isoformat() if offer.valid_to else None,
        "days_of_week": offer.days_of_week,
        "source_url": offer.source_url,
        "is_active_today": is_active_today(offer),
        "is_active_this_week": is_active_this_week(offer),
        "days_remaining": days_remaining,
    }


# ── Scraping ─────────────────────────────────────────────────────────────────
async def _do_scrape(bank_keys: List[str]) -> None:
    global _offers, _last_scraped, _scraping_in_progress, _scrape_errors

    _scraping_in_progress = True
    _scrape_errors = {}
    all_offers: List[Dict] = []

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])

            tasks = {key: BANKS[key]["fn"](browser) for key in bank_keys if key in BANKS}
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            for key, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    log.error("Scrape failed [%s]: %s", key, result)
                    _scrape_errors[key] = str(result)
                else:
                    for offer in result:
                        all_offers.append(_offer_to_dict(offer, key))

            await browser.close()

        # Load manual offers
        try:
            import importlib.util
            manual_path = Path(__file__).parent / "manual_offers.py"
            if manual_path.exists():
                spec = importlib.util.spec_from_file_location("manual_offers", manual_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for offer in getattr(mod, "MANUAL_OFFERS", []):
                    bkey = next((k for k, v in BANKS.items() if v["name"] == offer.bank), "manual")
                    all_offers.append(_offer_to_dict(offer, bkey))
        except Exception as e:
            log.warning("Manual offers load failed: %s", e)

        _offers = all_offers
        _last_scraped = datetime.now(TZ)
        _save_cache(all_offers)
        log.info("Scrape complete: %d offers", len(all_offers))

    except Exception as e:
        log.exception("Scrape run failed: %s", e)
        _scrape_errors["__scraper__"] = str(e)
    finally:
        _scraping_in_progress = False


# ── Scheduler ────────────────────────────────────────────────────────────────

def _next_scrape_time(now: datetime) -> datetime:
    """Return the next scheduled scrape time after *now* (Asia/Colombo).

    Slots: 06:00, 10:00, 14:00, 18:00, 22:00.
    If all today's slots have passed, the next slot is 06:00 tomorrow.
    """
    for h in SCRAPE_HOURS:
        candidate = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if candidate > now:
            return candidate
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=SCRAPE_HOURS[0], minute=0, second=0, microsecond=0)


_background_tasks: set = set()


async def _scheduler_loop() -> None:
    """Sleep until the next scheduled slot, run a scrape, repeat forever."""
    while True:
        now = datetime.now(TZ)
        next_run = _next_scrape_time(now)
        wait_secs = (next_run - now).total_seconds()
        log.info(
            "Next scheduled scrape at %s (in %.0f min)",
            next_run.strftime("%Y-%m-%d %H:%M %Z"),
            wait_secs / 60,
        )
        await asyncio.sleep(wait_secs)
        if not _scraping_in_progress:
            task = asyncio.create_task(_do_scrape(list(BANKS.keys())))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup() -> None:
    global _offers, _last_scraped
    cached, scraped_at = _load_cache()
    if cached and scraped_at:
        now = datetime.now(TZ)
        if scraped_at.tzinfo is None:
            try:
                scraped_at = scraped_at.replace(tzinfo=TZ)
            except Exception:
                pass
        try:
            age = now - scraped_at
        except TypeError:
            age = timedelta(hours=CACHE_TTL_HOURS + 1)

        if age.total_seconds() < CACHE_TTL_HOURS * 3600:
            _offers = cached
            _last_scraped = scraped_at
            log.info("Loaded %d offers from cache (age: %dm)", len(cached), age.seconds // 60)
            scheduler = asyncio.create_task(_scheduler_loop())
            _background_tasks.add(scheduler)
            scheduler.add_done_callback(_background_tasks.discard)
            return

    log.info("Cache stale or missing — scraping now")
    scrape_task = asyncio.create_task(_do_scrape(list(BANKS.keys())))
    _background_tasks.add(scrape_task)
    scrape_task.add_done_callback(_background_tasks.discard)
    scheduler = asyncio.create_task(_scheduler_loop())
    _background_tasks.add(scheduler)
    scheduler.add_done_callback(_background_tasks.discard)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.head("/api/status")
def head_status() -> Response:
    return Response(status_code=200)


@app.get("/api/status", response_model=ScrapeStatus)
def get_status() -> ScrapeStatus:
    age = None
    if _last_scraped:
        ts = _last_scraped
        if ts.tzinfo is None:
            try:
                ts = ts.replace(tzinfo=TZ)
            except Exception:
                pass
        try:
            age = int((datetime.now(TZ) - ts).total_seconds() / 60)
        except TypeError:
            age = None
    return ScrapeStatus(
        last_scraped=_last_scraped.isoformat() if _last_scraped else None,
        offer_count=len(_offers),
        scraping=_scraping_in_progress,
        errors=_scrape_errors,
        cache_age_minutes=age,
    )


@app.post("/api/scrape")
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    banks: str = Query(default=",".join(BANKS.keys())),
) -> Dict:
    global _scraping_in_progress
    if _scraping_in_progress:
        return {"status": "already_running"}
    bank_keys = [b.strip() for b in banks.split(",") if b.strip() in BANKS]
    background_tasks.add_task(_do_scrape, bank_keys)
    return {"status": "started", "banks": bank_keys}


@app.get("/api/offers")
def get_offers(
    banks: Optional[str] = Query(None),
    cards: Optional[str] = Query(None),
    supermarket: Optional[str] = Query(None),
    active_today: Optional[bool] = Query(None),
    active_week: Optional[bool] = Query(None),
) -> Dict:
    results = list(_offers)

    if banks:
        bank_keys = {b.strip().lower() for b in banks.split(",")}
        results = [o for o in results if o["bank_key"] in bank_keys]

    if cards and cards != "both":
        if cards == "credit":
            results = [o for o in results if "Credit" in o["card_type"]]
        elif cards == "debit":
            results = [o for o in results if "Debit" in o["card_type"]]

    if supermarket:
        sm_lower = supermarket.lower()
        results = [o for o in results if sm_lower in o["supermarket"].lower()]

    if active_today is True:
        results = [o for o in results if o["is_active_today"]]

    if active_week is True:
        results = [o for o in results if o["is_active_this_week"]]

    return {"offers": results, "total": len(results)}


@app.get("/api/banks")
def get_banks() -> Dict:
    return {"banks": [{"key": k, "name": v["name"]} for k, v in BANKS.items()]}


@app.get("/api/supermarkets")
def get_supermarkets() -> Dict:
    seen: Dict[str, int] = {}
    for o in _offers:
        sm = o["supermarket"]
        seen[sm] = seen.get(sm, 0) + 1
    return {"supermarkets": [{"name": k, "count": v} for k, v in sorted(seen.items())]}


@app.get("/api/ics")
def download_ics(
    banks: Optional[str] = Query(None),
    cards: Optional[str] = Query(None),
) -> Response:
    results = list(_offers)

    if banks:
        bank_keys = {b.strip().lower() for b in banks.split(",")}
        results = [o for o in results if o["bank_key"] in bank_keys]

    if cards and cards != "both":
        if cards == "credit":
            results = [o for o in results if "Credit" in o["card_type"]]
        elif cards == "debit":
            results = [o for o in results if "Debit" in o["card_type"]]

    offers: List[Offer] = []
    for o in results:
        offers.append(Offer(
            bank=o["bank"],
            supermarket=o["supermarket"],
            offer_text=o["offer_text"],
            card_type=o["card_type"],
            valid_from=date.fromisoformat(o["valid_from"]) if o["valid_from"] else None,
            valid_to=date.fromisoformat(o["valid_to"]) if o["valid_to"] else None,
            days_of_week=o["days_of_week"],
            source_url=o["source_url"],
        ))

    cal = build_ics(offers)
    return Response(
        content=cal.to_ical(),
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=lk_bank_offers.ics"},
    )


@app.get("/api/google-calendar-url")
def google_calendar_url(
    banks: Optional[str] = Query(None),
    cards: Optional[str] = Query(None),
) -> Dict:
    base = "http://localhost:8000/api/ics"
    params = []
    if banks:
        params.append("banks={}".format(banks))
    if cards:
        params.append("cards={}".format(cards))
    ics_url = base + ("?" + "&".join(params) if params else "")
    gc_url = "https://calendar.google.com/calendar/r/settings/addbyurl?url={}".format(ics_url)
    return {"ics_url": ics_url, "google_calendar_url": gc_url}


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
