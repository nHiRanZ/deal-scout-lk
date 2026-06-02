from __future__ import annotations
"""
manual_offers.py – Hand-curated offers to supplement / override the scraper.

When bank websites block scraping or change their HTML, add offers here.
Run: python scraper.py --manual-only  (see README for flag)
Or:  from manual_offers import MANUAL_OFFERS  (imported automatically by scraper)

Format reference:
─────────────────
Offer(
    bank         = "Bank Name",
    supermarket  = "Supermarket Name",
    offer_text   = "30% off total bill",          # short, human-readable
    card_type    = "Credit",                       # "Credit", "Debit", or "Credit / Debit"
    valid_from   = date(2025, 6, 1),               # or None
    valid_to     = date(2025, 6, 30),              # or None
    days_of_week = [0, 5, 6],                      # 0=Mon…6=Sun, empty=every day in window
    source_url   = "https://...",
)

Weekday reference:  Monday=0  Tuesday=1  Wednesday=2  Thursday=3
                    Friday=4  Saturday=5  Sunday=6
"""

from datetime import date
from scraper import Offer

MANUAL_OFFERS: list[Offer] = [
    # ── EXAMPLE ENTRIES (delete / update these) ──────────────────────────
    # Offer(
    #     bank="Sampath Bank",
    #     supermarket="Keells",
    #     offer_text="25% off total bill",
    #     card_type="Credit",
    #     valid_from=date(2025, 6, 1),
    #     valid_to=date(2025, 6, 30),
    #     days_of_week=[0, 1, 2, 3, 4],  # Weekdays
    #     source_url="https://www.sampath.lk/sampath-cards/credit-card-offer?firstTab=super_markets",
    # ),
    # Offer(
    #     bank="Seylan Bank",
    #     supermarket="Cargills Food City",
    #     offer_text="15% cashback",
    #     card_type="Credit / Debit",
    #     valid_from=date(2025, 6, 1),
    #     valid_to=date(2025, 6, 29),
    #     days_of_week=[0],  # Every Monday
    #     source_url="https://www.seylan.lk/promotions/cards/supermarket",
    # ),
]
