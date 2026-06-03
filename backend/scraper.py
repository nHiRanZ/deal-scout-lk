#!/usr/bin/env python3
from __future__ import annotations
"""
Sri Lanka Bank Supermarket Offers → Google Calendar ICS Generator
Scrapes offer data from major Sri Lankan bank websites and generates
an ICS file ready to import into Google Calendar.

Usage:
    python scraper.py [--banks bank1,bank2,...] [--cards credit|debit|both] [--output offers.ics]

Requirements:
    pip install playwright beautifulsoup4 icalendar python-dateutil lxml requests
    playwright install chromium
"""

import argparse
import asyncio
import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo

from bs4 import BeautifulSoup
from icalendar import Calendar, Event, vText
from playwright.async_api import async_playwright, Page, Browser

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

TZ = ZoneInfo("Asia/Colombo")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scraper")


# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────

@dataclass
class Offer:
    """Represents a single bank supermarket offer."""
    bank: str
    supermarket: str
    offer_text: str          # e.g. "30% off total bill"
    card_type: str           # "Credit", "Debit", or "Credit / Debit"
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    days_of_week: List[int] = field(default_factory=list)   # 0=Mon … 6=Sun
    source_url: str = ""
    raw_terms: str = ""

    @property
    def title(self) -> str:
        """ICS event title formatted per spec."""
        return f"{self.supermarket} | {self.offer_text} | {self.bank} | {self.card_type}"


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

SUPERMARKET_KEYWORDS: Dict[str, List[str]] = {
    "Keells": ["keells", "keell's", "keell's super"],
    "Cargills Food City": ["cargills", "food city", "cargill's"],
    "Laugfs": ["laugfs", "laughs super", "laughs"],
    "Arpico Super Centre": ["arpico"],
    "Spar": ["spar"],
    "Glomark": ["glomark"],
}

WEEKDAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
    "weekday": [0, 1, 2, 3, 4],
    "weekend": [5, 6],
    "every day": [0, 1, 2, 3, 4, 5, 6],
    "daily": [0, 1, 2, 3, 4, 5, 6],
}

MONTH_NAMES = {
    "january": 1, "jan": 1, "february": 2, "feb": 2,
    "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def detect_supermarket(text: str) -> Optional[str]:
    """Return the canonical supermarket name if found in text, else None."""
    tl = text.lower()
    for name, keywords in SUPERMARKET_KEYWORDS.items():
        if any(kw in tl for kw in keywords):
            return name
    return None


def clean_text(text: str) -> str:
    """Strip unrendered template tokens and stray HTML artifacts."""
    text = re.sub(r'\bslug\}\}[">]*', '', text)   # Seylan: slug}}"&gt; prefix
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


_CARD_NOISE = re.compile(
    r'\s+(?:'
    r'with\s+(?:your\b|all\b|\w+\s+(?:Credit|Debit|Visa|Mastercard|Infinite|Premier|Gold|Platinum)\b)|'
    r'for\s+all\s+\w+'
    r')',
    re.I,
)

def extract_offer_text(text: str) -> str:
    """
    Extract a descriptive offer line: discount + what it applies to.
    Includes conditions like 'for bills over Rs. X' but drops card eligibility
    noise like 'with your Seylan Infinite Credit Card' or 'for all Sampath cardholders'.
    """
    text = re.sub(r'^\s*(?:enjoy|get|save|avail|offer\s*\d*:?)\s+', '', text, flags=re.I)
    text = text.split('\n')[0].strip()  # take only first line

    pct_m = re.search(
        r'(?:up\s*to\s+|upto\s+)?\d+(?:\.\d+)?\s*%(?:\s*(?:off|discount|cashback|back|savings))?',
        text, re.I,
    )
    if not pct_m:
        return text[:100].strip()

    snippet = text[pct_m.start():]
    cut = _CARD_NOISE.search(snippet)
    if cut:
        snippet = snippet[:cut.start()]

    return snippet.strip()[:120]


def parse_days(text: str) -> List[int]:
    """Extract days-of-week from offer text."""
    tl = text.lower()
    days: List[int] = []
    for word, val in WEEKDAY_NAMES.items():
        if word in tl:
            if isinstance(val, list):
                days.extend(val)
            else:
                days.append(val)
    return sorted(set(days))


def parse_date(text: str) -> Optional[date]:
    """Try to parse a date from strings like '30th June 2025', 'June 30, 2025'."""
    # Normalise ordinals
    text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text, flags=re.I)
    patterns = [
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",   # 30 June 2025
        r"([A-Za-z]+)\s+(\d{1,2})[,\s]+(\d{4})", # June 30, 2025
        r"(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})", # 2025-06-30
        r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})", # 30/06/2025
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        g = m.groups()
        try:
            if re.match(r"\d{4}", g[0]):              # ISO
                return date(int(g[0]), int(g[1]), int(g[2]))
            elif re.match(r"[A-Za-z]", g[0]):         # Month-first
                mon = MONTH_NAMES.get(g[0].lower())
                if mon:
                    return date(int(g[2]), mon, int(g[1]))
            elif re.match(r"[A-Za-z]", g[1]):         # Day Month Year
                mon = MONTH_NAMES.get(g[1].lower())
                if mon:
                    return date(int(g[2]), mon, int(g[0]))
            else:                                      # DD/MM/YYYY
                return date(int(g[2]), int(g[1]), int(g[0]))
        except (ValueError, KeyError):
            continue
    return None


def parse_date_range(text: str) -> Tuple[Optional[date], Optional[date]]:
    """Extract (from, to) dates from offer text. 'valid until', 'until', 'to', etc."""
    # Look for "from X to Y" / "X – Y"
    range_m = re.search(
        r"(?:from|valid from)?\s*(.+?)\s*(?:to|until|–|-)\s*(.+?)(?:\.|,|$)",
        text, re.I
    )
    if range_m:
        d1 = parse_date(range_m.group(1))
        d2 = parse_date(range_m.group(2))
        if d1 or d2:
            return d1, d2

    # Single date with "until/valid until/expires"
    until_m = re.search(r"(?:until|valid until|valid till|expires?(?:s)?\s+on|till)\s+(.+?)(?:\.|,|$)", text, re.I)
    if until_m:
        d = parse_date(until_m.group(1))
        return None, d

    # Any lone date
    d = parse_date(text)
    return None, d


def detect_card_type(text: str) -> str:
    tl = text.lower()
    has_credit = "credit" in tl
    has_debit = "debit" in tl
    if has_credit and has_debit:
        return "Credit / Debit"
    elif has_debit:
        return "Debit"
    elif has_credit:
        return "Credit"
    return "Credit"  # default assumption for bank offer pages


def generate_event_dates(offer: Offer) -> List[date]:
    """
    Expand an offer into a list of calendar dates.
    - If days_of_week given → one event per matching weekday in the validity window
    - Else → one all-day event spanning valid_from to valid_to
    """
    today = date.today()
    start = offer.valid_from or today
    end = offer.valid_to or (today + timedelta(days=90))  # fallback: 3 months ahead

    if start > end:
        end = start

    if not offer.days_of_week:
        return [start]  # single multi-day event handled separately

    dates: List[date] = []
    current = start
    while current <= end:
        if current.weekday() in offer.days_of_week:
            dates.append(current)
        current += timedelta(days=1)
    return dates


# ─────────────────────────────────────────────
# Browser helper
# ─────────────────────────────────────────────

async def fetch_page(
    browser: Browser,
    url: str,
    wait_selector: Optional[str] = None,
    extra_wait: int = 3_000,
) -> BeautifulSoup:
    """Fetch a JS-rendered page and return BeautifulSoup."""
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
    )
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    page: Page = await context.new_page()
    try:
        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        })
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=15_000)
            except Exception:
                pass
        await page.wait_for_timeout(extra_wait)
        html = await page.content()
        return BeautifulSoup(html, "lxml")
    finally:
        await page.close()
        await context.close()


# ─────────────────────────────────────────────
# Per-bank Scrapers
# ─────────────────────────────────────────────

async def scrape_sampath(browser: Browser) -> List[Offer]:
    """Sampath Bank – credit card offers, supermarket tab."""
    url = "https://www.sampath.lk/sampath-cards/credit-card-offer?firstTab=super_markets"
    log.info("Scraping Sampath Bank...")
    soup = await fetch_page(browser, url, wait_selector=".card-offer-block")
    offers: List[Offer] = []

    blocks = soup.find_all("div", class_=lambda c: c and "card-offer-block" in c)
    for block in blocks:
        discount_el = block.find("div", class_=lambda c: c and "discount" in c)
        place_el = block.find("p", class_=lambda c: c and "place" in c)
        date_el = block.find("p", class_=lambda c: c and "date" in c)
        name_el = block.find("div", class_=lambda c: c and "card-name" in c)

        discount_text = discount_el.get_text(strip=True) if discount_el else ""
        place_text = place_el.get_text(strip=True) if place_el else ""
        date_text = date_el.get_text(strip=True) if date_el else ""
        full_text = name_el.get_text(separator=" ", strip=True) if name_el else ""

        if not discount_text and not place_text:
            continue

        sm = detect_supermarket(place_text) or detect_supermarket(full_text)
        if sm is None:
            continue
        offer_text = extract_offer_text(full_text) or extract_offer_text(discount_text)
        days = parse_days(date_text)
        _, to_d = parse_date_range(date_text)
        card = detect_card_type(full_text)

        offers.append(Offer(
            bank="Sampath Bank",
            supermarket=sm,
            offer_text=offer_text,
            card_type=card,
            valid_from=None,
            valid_to=to_d,
            days_of_week=days,
            source_url=url,
            raw_terms=(date_text + " " + full_text)[:500],
        ))

    log.info(f"  Sampath → {len(offers)} offers")
    return offers


async def scrape_seylan(browser: Browser) -> List[Offer]:
    """Seylan Bank – promotions/cards/supermarket."""
    url = "https://www.seylan.lk/promotions/cards/supermarket"
    log.info("Scraping Seylan Bank...")
    soup = await fetch_page(browser, url, wait_selector=".new-promotion-card-body")
    offers: List[Offer] = []

    for card in soup.find_all("div", class_="new-promotion-card-body"):
        title_el = card.find("h5", class_="new-promotion-title")
        desc_el = card.find("p", class_="new-promotion-dis")
        date_el = card.find("p", class_="new-promotion-date")
        link_el = card.find("a", class_="new-promotion-btn")

        title = clean_text(title_el.get_text(strip=True)) if title_el else ""
        desc = clean_text(desc_el.get_text(strip=True)) if desc_el else ""
        date_text = clean_text(date_el.get_text(strip=True)) if date_el else ""
        source = link_el["href"] if link_el and link_el.get("href") else url
        full_text = f"{title} {desc} {date_text}"

        sm = detect_supermarket(full_text)
        if sm is None:
            continue

        offer_text = extract_offer_text(desc) or extract_offer_text(title)

        days = parse_days(full_text)
        _, to_d = parse_date_range(date_text or full_text)

        offers.append(Offer(
            bank="Seylan Bank",
            supermarket=sm,
            offer_text=offer_text,
            card_type=detect_card_type(full_text),
            valid_from=None,
            valid_to=to_d,
            days_of_week=days,
            source_url=source,
            raw_terms=full_text[:500],
        ))

    log.info(f"  Seylan Bank → {len(offers)} offers")
    return offers


async def scrape_combank(browser: Browser) -> List[Offer]:
    """Commercial Bank – only the #supermarket section of rewards-promotions."""
    url = "https://www.combank.lk/rewards-promotions"
    log.info("Scraping Commercial Bank...")
    soup = await fetch_page(browser, url, wait_selector="#supermarket")
    offers: List[Offer] = []

    sm_section = soup.find(id="supermarket")
    if not sm_section:
        log.warning("  ComBank: #supermarket section not found")
        return offers

    for reward in sm_section.find_all("a", class_=lambda c: c and "reward" in c):
        h3 = reward.find("h3")
        date_el = reward.find("p", class_="valid-date")
        tag = reward.find("div", class_="offer-tag")

        title = h3.get_text(strip=True) if h3 else ""
        date_text = date_el.get_text(strip=True) if date_el else ""
        tag_text = tag.get_text(separator=" ", strip=True) if tag else ""
        full_text = title + " " + date_text

        sm = detect_supermarket(full_text)
        if sm is None:
            continue

        offer_text = extract_offer_text(tag_text)

        days = parse_days(date_text)
        _, to_d = parse_date_range(date_text)

        offers.append(Offer(
            bank="Commercial Bank",
            supermarket=sm,
            offer_text=offer_text,
            card_type="Credit",
            valid_from=None,
            valid_to=to_d,
            days_of_week=days,
            source_url=reward.get("href", url),
            raw_terms=full_text[:500],
        ))

    log.info(f"  Commercial Bank → {len(offers)} offers")
    return offers


async def scrape_ntb(browser: Browser) -> List[Offer]:
    """Nations Trust Bank – table of merchant / offer / eligibility."""
    url = "https://www.nationstrust.com/promotions/enjoy-exclusive-savings-on-supermarkets"
    log.info("Scraping Nations Trust Bank (NTB)...")
    soup = await fetch_page(browser, url, wait_selector="section.promotion-detail table")
    offers: List[Offer] = []

    detail = soup.find("section", class_=re.compile(r"promotion-detail", re.I))
    if not detail:
        return offers

    for row in detail.find_all("tr")[1:]:  # skip header row
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        merchant = cells[0].get_text(strip=True)
        offer_raw = cells[1].get_text(separator=" ", strip=True)
        eligibility = cells[2].get_text(separator=" ", strip=True) if len(cells) > 2 else ""

        sm = detect_supermarket(merchant) or detect_supermarket(offer_raw)
        if sm is None:
            continue

        days = parse_days(eligibility)
        _, to_d = parse_date_range(eligibility)
        offers.append(Offer(
            bank="Nations Trust Bank",
            supermarket=sm,
            offer_text=extract_offer_text(offer_raw),
            card_type=detect_card_type(offer_raw + " " + eligibility),
            valid_from=None,
            valid_to=to_d,
            days_of_week=days,
            source_url=url,
            raw_terms=(offer_raw + " " + eligibility)[:500],
        ))

    log.info(f"  Nations Trust Bank → {len(offers)} offers")
    return offers


async def scrape_hnb(browser: Browser) -> List[Offer]:
    """Hatton National Bank – React SPA with Tailwind classes."""
    url = "https://www.hnb.lk/card-promotion?category=Shopping"
    log.info("Scraping Hatton National Bank (HNB)...")
    # Wait for the offer h4s (class includes "text-primary") to appear
    soup = await fetch_page(browser, url, wait_selector="h4[class*='text-primary']", extra_wait=15_000)
    offers: List[Offer] = []

    seen: set = set()
    for h4 in soup.find_all("h4", class_=lambda c: c and "text-primary" in c):
        title = h4.get_text(strip=True)
        if title in seen:
            continue
        seen.add(title)

        sm = detect_supermarket(title)
        if sm is None:
            continue

        # Date h4 is a direct sibling within the same card div
        date_h4 = h4.find_next_sibling("h4")
        date_text = date_h4.get_text(strip=True) if date_h4 else ""

        days = parse_days(title + " " + date_text)
        _, to_d = parse_date_range(date_text)
        offers.append(Offer(
            bank="Hatton National Bank",
            supermarket=sm,
            offer_text=extract_offer_text(title),
            card_type="Credit",
            valid_from=None,
            valid_to=to_d,
            days_of_week=days,
            source_url=url,
            raw_terms=(title + " " + date_text)[:500],
        ))

    log.info(f"  Hatton National Bank → {len(offers)} offers")
    return offers


async def scrape_boc(browser: Browser) -> List[Offer]:
    """Bank of Ceylon – Swiper slider of a.swiper-slide.product cards."""
    url = "https://www.boc.lk/personal-banking/card-offers/supermarkets"
    log.info("Scraping Bank of Ceylon (BOC)...")
    soup = await fetch_page(browser, url, wait_selector="a.swiper-slide")
    offers: List[Offer] = []

    for slide in soup.find_all("a", class_=lambda c: c and "swiper-slide" in c and "product" in c):
        h4 = slide.find("h4")
        desc_el = slide.find("div", class_="description")
        expiry_table = slide.find("table", class_="highligh-box")

        merchant = h4.get_text(strip=True) if h4 else ""
        desc = desc_el.get_text(separator=" ", strip=True) if desc_el else ""
        expiry_text = expiry_table.get_text(separator=" ", strip=True) if expiry_table else ""
        full_text = merchant + " " + desc

        sm = detect_supermarket(full_text)
        if sm is None:
            continue

        _, to_d = parse_date_range(expiry_text)
        offers.append(Offer(
            bank="Bank of Ceylon",
            supermarket=sm,
            offer_text=extract_offer_text(desc),
            card_type="Credit",
            valid_from=None,
            valid_to=to_d,
            days_of_week=parse_days(desc + " " + expiry_text),
            source_url=slide.get("href", url),
            raw_terms=(full_text + " " + expiry_text)[:500],
        ))

    log.info(f"  Bank of Ceylon → {len(offers)} offers")
    return offers


async def scrape_dfcc(browser: Browser) -> List[Offer]:
    """Scrapes dfcc.lk/supermarkets-credit — cardOfferText holds the offer sentence."""
    bank = "DFCC Bank"
    url = "https://www.dfcc.lk/supermarkets-credit"
    log.info("Scraping %s...", bank)
    soup = await fetch_page(browser, url, wait_selector="p.cardOfferText", extra_wait=12_000)
    offers: List[Offer] = []

    cards = soup.find_all("a", class_="cardd")
    offer_texts = soup.find_all("p", class_="cardOfferText")
    log.info("  DFCC debug: a.cardd=%d  p.cardOfferText=%d  page-title=%r",
             len(cards), len(offer_texts),
             soup.title.string.strip() if soup.title else "none")

    for card in cards:
        text_el = card.find("p", class_="cardOfferText")
        valid_el = card.find("p", class_="cardOfferValid")
        if not text_el:
            continue

        raw_text = text_el.get_text(separator=" ", strip=True)
        date_text = valid_el.get_text(separator=" ", strip=True) if valid_el else ""

        sm = detect_supermarket(raw_text)
        if sm is None:
            continue

        cleaned = re.sub(r'\s+with\s+DFCC\s+.*$', '', raw_text, flags=re.I).strip()
        offers.append(Offer(
            bank=bank,
            supermarket=sm,
            offer_text=extract_offer_text(cleaned) or cleaned[:120],
            card_type="Credit",
            valid_from=None,
            valid_to=parse_date_range(date_text)[1],
            days_of_week=parse_days(date_text),
            source_url=card.get("href", url),
            raw_terms=(raw_text + " " + date_text)[:500],
        ))

    if not offers:
        log.warning("  DFCC: specific selectors found nothing — falling back to generic scraper")
        offers = _generic_scrape(soup, bank, url)

    log.info("  %s → %d offers", bank, len(offers))
    return offers


def _parse_peoples_card(card, url: str, default_card: str) -> Optional[Offer]:
    """Extract one offer from a People's Bank article.offer-card element."""
    merchant_el = card.find(class_="promo-short")
    desc_el = card.find(class_="merchant-name")
    date_el = card.find(class_="valid-date")

    merchant = merchant_el.get_text(strip=True) if merchant_el else ""
    # Take only the first line — the rest is fine-print conditions
    desc_raw = desc_el.get_text(strip=True) if desc_el else ""
    desc = desc_raw.split('\n')[0].strip()
    # Remove "...See more" suffix
    desc = re.sub(r'\s*\.{3}See more$', '', desc, flags=re.I).strip()
    date_text = date_el.get_text(separator=" ", strip=True) if date_el else ""

    full_text = merchant + " " + desc
    sm = detect_supermarket(full_text)
    if sm is None:
        return None

    return Offer(
        bank="People's Bank",
        supermarket=sm,
        offer_text=extract_offer_text(desc) or desc[:80],
        card_type=default_card,
        valid_from=None,
        valid_to=parse_date_range(date_text)[1],
        days_of_week=parse_days(date_text),
        source_url=url,
        raw_terms=(full_text + " " + date_text)[:500],
    )


async def scrape_peoples(browser: Browser) -> List[Offer]:
    """People's Bank – supermarket offers (credit + debit)."""
    log.info("Scraping People's Bank...")
    offers: List[Offer] = []
    for card_type, url in [
        ("Credit", "https://www.peoplesbank.lk/promotion-category/supermarkets/?cardType=credit_card"),
        ("Debit",  "https://www.peoplesbank.lk/promotion-category/supermarkets/?cardType=debit_card"),
    ]:
        soup = await fetch_page(browser, url, wait_selector="article.offer-card")
        for card in soup.find_all("article", class_="offer-card"):
            offer = _parse_peoples_card(card, url, card_type)
            if offer:
                offers.append(offer)

    log.info(f"  People's Bank → {len(offers)} offers")
    return offers


def _generic_scrape(
    soup: BeautifulSoup,
    bank: str,
    url: str,
    default_card: str = "Credit",
) -> List[Offer]:
    """
    Generic offer extractor that tries multiple common HTML patterns
    and falls back to paragraph / heading scanning.
    """
    offers: List[Offer] = []

    # --- Strategy 1: structured offer/promo cards ---
    candidate_selectors = [
        {"class": re.compile(r"offer|promo|promotion|deal|card-item|tile", re.I)},
        "article",
        {"class": re.compile(r"post|entry|item", re.I)},
    ]
    blocks: list = []
    for sel in candidate_selectors:
        if isinstance(sel, str):
            blocks = soup.find_all(sel)
        else:
            blocks = soup.find_all(True, attrs=sel)
        if blocks:
            break

    for block in blocks:
        text = block.get_text(separator=" ", strip=True)
        if len(text) < 25:
            continue
        offer = _parse_offer_block(text, bank, url, default_card)
        if offer:
            offers.append(offer)

    # --- Strategy 2: headings + next sibling paragraph ---
    if not offers:
        for h in soup.find_all(["h2", "h3", "h4"]):
            h_text = h.get_text(strip=True)
            sibling = h.find_next_sibling(["p", "div", "ul"])
            combined = h_text + " " + (sibling.get_text(separator=" ", strip=True) if sibling else "")
            offer = _parse_offer_block(combined, bank, url, default_card)
            if offer:
                offers.append(offer)

    # --- Strategy 3: scan all paragraphs for discount keywords ---
    if not offers:
        for p in soup.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if re.search(r"\d+\s*%|discount|cashback|off", text, re.I):
                offer = _parse_offer_block(text, bank, url, default_card)
                if offer:
                    offers.append(offer)

    # Deduplicate on (supermarket, offer_text)
    seen: set[str] = set()
    unique: List[Offer] = []
    for o in offers:
        key = f"{o.supermarket}|{o.offer_text[:40]}"
        if key not in seen:
            seen.add(key)
            unique.append(o)

    log.info(f"  {bank} → {len(unique)} offers")
    return unique


def _parse_offer_block(text: str, bank: str, url: str, default_card: str) -> Optional[Offer]:
    """Parse a text block into an Offer, returning None if it looks irrelevant."""
    if len(text) < 20:
        return None
    sm = detect_supermarket(text)
    if sm is None:
        return None
    if not re.search(r"\d+\s*%|discount|cashback|off|savings|special", text, re.I):
        return None
    offer_text = extract_offer_text(text) or text[:60].strip()
    from_d, to_d = parse_date_range(text)
    days = parse_days(text)
    card = detect_card_type(text) if "credit" in text.lower() or "debit" in text.lower() else default_card

    return Offer(
        bank=bank,
        supermarket=sm,
        offer_text=offer_text,
        card_type=card,
        valid_from=from_d,
        valid_to=to_d,
        days_of_week=days,
        source_url=url,
        raw_terms=text[:500],
    )


# ─────────────────────────────────────────────
# Bank registry
# ─────────────────────────────────────────────

BANKS: Dict[str, Dict] = {
    "sampath": {"name": "Sampath Bank",        "fn": scrape_sampath},
    "seylan":  {"name": "Seylan Bank",         "fn": scrape_seylan},
    "combank": {"name": "Commercial Bank",     "fn": scrape_combank},
    "ntb":     {"name": "Nations Trust Bank",  "fn": scrape_ntb},
    "hnb":     {"name": "Hatton National Bank","fn": scrape_hnb},
    "boc":     {"name": "Bank of Ceylon",      "fn": scrape_boc},
    "dfcc":    {"name": "DFCC Bank",           "fn": scrape_dfcc},
    "peoples": {"name": "People's Bank",       "fn": scrape_peoples},
}


# ─────────────────────────────────────────────
# ICS Generator
# ─────────────────────────────────────────────

def build_ics(offers: List[Offer]) -> Calendar:
    """Convert offers list into an icalendar Calendar object."""
    cal = Calendar()
    cal.add("prodid", "-//LK Bank Supermarket Offers//EN")
    cal.add("version", "2.0")
    cal.add("X-WR-CALNAME", "🛒 LK Bank Supermarket Offers")
    cal.add("X-WR-TIMEZONE", "Asia/Colombo")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("METHOD", "PUBLISH")

    today = date.today()
    event_count = 0

    for offer in offers:
        start = offer.valid_from or today
        end = offer.valid_to or (today + timedelta(days=90))

        if offer.days_of_week:
            # Create individual events for each matching weekday
            event_dates = generate_event_dates(offer)
            for evt_date in event_dates:
                event = _make_event(offer, evt_date, evt_date + timedelta(days=1))
                cal.add_component(event)
                event_count += 1
        else:
            # Single all-day event spanning the validity window
            event = _make_event(offer, start, end + timedelta(days=1))
            cal.add_component(event)
            event_count += 1

    log.info(f"Generated {event_count} calendar events from {len(offers)} offers.")
    return cal


def _make_event(offer: Offer, dtstart: date, dtend: date) -> Event:
    """Build a single iCalendar Event."""
    event = Event()

    # Deterministic UID so re-imports don't duplicate
    uid_seed = f"{offer.bank}|{offer.supermarket}|{offer.offer_text}|{dtstart.isoformat()}"
    uid = hashlib.md5(uid_seed.encode()).hexdigest() + "@lk-bank-offers"
    event.add("uid", uid)

    event.add("summary", vText(offer.title))
    event.add("dtstart", dtstart)
    event.add("dtend", dtend)
    event.add("dtstamp", datetime.now(tz=TZ))

    desc_lines = [
        f"Bank: {offer.bank}",
        f"Card Type: {offer.card_type}",
        f"Supermarket: {offer.supermarket}",
        f"Offer: {offer.offer_text}",
    ]
    if offer.valid_from:
        desc_lines.append(f"Valid From: {offer.valid_from.strftime('%d %B %Y')}")
    if offer.valid_to:
        desc_lines.append(f"Valid Until: {offer.valid_to.strftime('%d %B %Y')}")
    if offer.raw_terms:
        desc_lines.append(f"\nTerms: {offer.raw_terms[:300]}")
    desc_lines.append(f"\nSource: {offer.source_url}")

    event.add("description", "\n".join(desc_lines))
    event.add("url", offer.source_url)

    # Color category hint (Google Calendar reads X-MICROSOFT-CDO-BUSYSTATUS but
    # category-based colour requires a label – we use categories instead)
    category_map = {
        "Sampath Bank": "Sampath",
        "Seylan Bank": "Seylan",
        "Commercial Bank": "ComBank",
        "Nations Trust Bank": "NTB",
        "Hatton National Bank": "HNB",
        "Bank of Ceylon": "BOC",
        "DFCC Bank": "DFCC",
        "People's Bank": "Peoples",
    }
    event.add("categories", [category_map.get(offer.bank, offer.bank), offer.card_type])

    return event


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

async def main(selected_banks: List[str], card_filter: str, output_path: str):
    all_offers: List[Offer] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        tasks = []
        for key in selected_banks:
            if key in BANKS:
                tasks.append((key, BANKS[key]["fn"](browser)))
            else:
                log.warning(f"Unknown bank key: {key!r} – skipping.")

        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        for (key, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                log.error(f"Failed to scrape {BANKS[key]['name']}: {result}")
            else:
                all_offers.extend(result)

        await browser.close()

    # Apply card type filter
    if card_filter == "credit":
        all_offers = [o for o in all_offers if "Credit" in o.card_type]
    elif card_filter == "debit":
        all_offers = [o for o in all_offers if "Debit" in o.card_type]

    log.info(f"Total offers after filtering: {len(all_offers)}")

    if not all_offers:
        log.warning("No offers found. The bank websites may have changed their HTML structure.")
        log.warning("Check SCRAPING_NOTES.md for manual override instructions.")
        # Still write empty calendar so the file is created
    
    cal = build_ics(all_offers)

    Path(output_path).write_bytes(cal.to_ical())
    log.info(f"✅  ICS file written: {output_path}")
    log.info(f"    Import into Google Calendar: Calendar Settings → Import → select the .ics file")

    # Also write a JSON summary for debugging / future web app use
    summary = [
        {
            "bank": o.bank,
            "supermarket": o.supermarket,
            "offer": o.offer_text,
            "card_type": o.card_type,
            "valid_from": o.valid_from.isoformat() if o.valid_from else None,
            "valid_to": o.valid_to.isoformat() if o.valid_to else None,
            "days_of_week": o.days_of_week,
            "source": o.source_url,
        }
        for o in all_offers
    ]
    json_path = output_path.replace(".ics", "_debug.json")
    Path(json_path).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    log.info(f"    Debug JSON: {json_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape Sri Lankan bank supermarket offers → ICS file"
    )
    parser.add_argument(
        "--banks",
        default=",".join(BANKS.keys()),
        help=f"Comma-separated bank keys. Available: {', '.join(BANKS.keys())}",
    )
    parser.add_argument(
        "--cards",
        choices=["credit", "debit", "both"],
        default="both",
        help="Card type filter (default: both)",
    )
    parser.add_argument(
        "--output",
        default="lk_bank_offers.ics",
        help="Output ICS file path (default: lk_bank_offers.ics)",
    )
    parser.add_argument(
        "--manual-only",
        action="store_true",
        help="Skip web scraping; use only entries in manual_offers.py",
    )
    parser.add_argument(
        "--include-manual",
        action="store_true",
        default=True,
        help="Merge manual_offers.py entries with scraped data (default: True)",
    )
    args = parser.parse_args()

    selected = [b.strip().lower() for b in args.banks.split(",")]

    # Load manual offers if the file exists
    manual: List[Offer] = []
    manual_path = Path(__file__).parent / "manual_offers.py"
    if manual_path.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("manual_offers", manual_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            manual = getattr(mod, "MANUAL_OFFERS", [])
            log.info(f"Loaded {len(manual)} manual offer(s) from manual_offers.py")
        except Exception as e:
            log.warning(f"Could not load manual_offers.py: {e}")

    if args.manual_only:
        # Skip scraping entirely
        card_filter = args.cards
        if card_filter == "credit":
            manual = [o for o in manual if "Credit" in o.card_type]
        elif card_filter == "debit":
            manual = [o for o in manual if "Debit" in o.card_type]
        cal = build_ics(manual)
        Path(args.output).write_bytes(cal.to_ical())
        log.info(f"✅  ICS written (manual only): {args.output}")
    else:
        async def _run():
            await main(selected, args.cards, args.output)
            # Merge manual offers into the ICS
            if manual and args.include_manual:
                log.info("Merging manual offers into ICS...")
                # Re-read, re-build with manual appended
                existing_cal = Calendar.from_ical(Path(args.output).read_bytes())
                all_off: List[Offer] = manual[:]
                cal2 = build_ics(all_off)
                # Append manual events to the written file (simpler: rebuild from scratch)
                # Already done via main(); here we just append manual events
                cal3 = Calendar.from_ical(Path(args.output).read_bytes())
                extra_cal = build_ics(manual)
                for component in extra_cal.walk():
                    if component.name == "VEVENT":
                        cal3.add_component(component)
                Path(args.output).write_bytes(cal3.to_ical())
                log.info(f"  Added {len(manual)} manual offer(s) to ICS.")
        asyncio.run(_run())
