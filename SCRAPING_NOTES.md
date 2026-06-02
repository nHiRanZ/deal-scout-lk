# Scraping Notes — Deal Scout LK

Per-bank scraping details, known failure modes, and workarounds.
When a bank blocks scraping or changes its HTML, add notes here and update `backend/manual_offers.py`.

---

## General notes

- All scrapers use Playwright + headless Chromium.
- Each scraper gets a fresh browser **context** (not a fresh browser instance) to isolate cookies and fingerprint state.
- A `navigator.webdriver = undefined` override is injected into every context to reduce bot-detection flags.
- The default page-load timeout is 40 s; the extra idle wait (after selector fires) defaults to 3 s but can be raised per-bank.
- Scrapers are run concurrently via `asyncio.gather`. One scraper timing out does not block others.

---

## Sampath Bank

**Key:** `sampath`
**URL:** `https://www.sampath.lk/sampath-cards/credit-card-offer?firstTab=super_markets`
**Wait selector:** `.card-offer-block`

### HTML structure
Offer blocks are `div.card-offer-block`. Inside each:
- `.discount` → discount percentage
- `p.place` → merchant/supermarket name
- `p.date` → validity dates and applicable days
- `div.card-name` → full offer description

### Known issues
- The `firstTab=super_markets` query param pre-selects the supermarkets tab; if removed, only the first tab loads and no supermarket offers appear.
- Some offer blocks have empty `.discount` and `.place` — these are skipped.

### Manual override trigger
If CSS class names change (e.g. `card-offer-block` → `offer-block`), the wait selector will time out and the scraper returns 0 offers.

---

## Seylan Bank

**Key:** `seylan`
**URL:** `https://www.seylan.lk/promotions/cards/supermarket`
**Wait selector:** `.new-promotion-card-body`

### HTML structure
Promotion cards are `div.new-promotion-card-body`. Inside each:
- `h5.new-promotion-title` → offer title
- `p.new-promotion-dis` → offer description
- `p.new-promotion-date` → validity period
- `a.new-promotion-btn` → link to the individual offer page (used as `source_url`)

### Known issues
- Some title and description strings contain unrendered template tokens like `slug}}"&gt;`. The `clean_text()` helper strips these.
- The description sometimes contains multi-line text; only the first line is used.

---

## Commercial Bank

**Key:** `combank`
**URL:** `https://www.combank.lk/rewards-promotions`
**Wait selector:** `#supermarket`

### HTML structure
The page has anchor-tag sections. The scraper targets `#supermarket` specifically and ignores all other sections (dining, travel, etc.).

Inside `#supermarket`, offer links are `a[class*=reward]`. Inside each:
- `h3` → merchant/title
- `p.valid-date` → validity dates
- `div.offer-tag` → discount percentage text

### Known issues
- The `#supermarket` anchor is rendered client-side. If the page SPA router changes this hash, the section won't be found and the scraper returns 0 offers with a warning.
- Card type is hardcoded to `"Credit"` because this page only lists credit card offers.

---

## Nations Trust Bank (NTB)

**Key:** `ntb`
**URL:** `https://www.nationstrust.com/promotions/enjoy-exclusive-savings-on-supermarkets`
**Wait selector:** `section.promotion-detail table`

### HTML structure
A `section.promotion-detail` contains an HTML table. Columns (0-indexed):
- 0 → merchant name
- 1 → offer text
- 2 → eligibility (card type, days, dates)

The first row is a header and is skipped.

### Known issues
- The promotion URL is very specific (a slug-based page). If NTB restructures their promotions site, the URL will 404.
- When the `section.promotion-detail` element is absent, the scraper returns an empty list silently.

---

## Hatton National Bank (HNB)

**Key:** `hnb`
**URL:** `https://www.hnb.lk/card-promotion?category=Shopping`
**Wait selector:** `h4[class*='text-primary']`
**Extra wait:** 6 000 ms (higher than default — React SPA needs extra time to render)

### HTML structure
The page is a React SPA with Tailwind CSS. Offer titles are `h4` elements whose class includes `text-primary`. The date/validity heading is the immediately following `h4` sibling.

### Known issues
- The 6 s extra wait is needed because the SPA renders asynchronously after `domcontentloaded`. Reducing this causes 0 offers.
- Tailwind class names are generated/purged — the selector `h4[class*='text-primary']` may break if HNB updates their Tailwind config.
- Deduplicated on `title` string before supermarket detection, because the SPA sometimes renders duplicate cards.

---

## Bank of Ceylon (BOC)

**Key:** `boc`
**URL:** `https://www.boc.lk/personal-banking/card-offers/supermarkets`
**Wait selector:** `a.swiper-slide`

### HTML structure
Offers are in a Swiper.js slider. Each slide is `a.swiper-slide.product`. Inside each slide:
- `h4` → merchant name
- `div.description` → offer description
- `table.highligh-box` (note typo in class name) → expiry/terms

### Known issues
- The Swiper library renders duplicate slide clones for the infinite-scroll effect. The supermarket detection filter naturally deduplicates these (same text → same offer).
- The class typo `highligh-box` (missing 't') is intentional — it matches the actual HTML.
- Card type is hardcoded to `"Credit"`.

---

## DFCC Bank

**Key:** `dfcc`
**URL:** `https://www.dfcc.lk/supermarkets-credit`
**Wait selector:** `p.cardOfferText`
**Extra wait:** 5 000 ms

### HTML structure
Offers are `a.cardd` links. Inside each:
- `p.cardOfferText` → full offer sentence including merchant name
- `p.cardOfferValid` → validity period

### Known issues
- The offer text often ends with `" with DFCC Visa/Mastercard..."`. The scraper strips this suffix with a regex before calling `extract_offer_text()`.
- The 5 s extra wait is required; the page lazy-loads offer cards after the main DOM is ready.
- Card type is hardcoded to `"Credit"` (DFCC only lists credit card supermarket offers on this URL).

---

## People's Bank

**Key:** `peoples`
**URLs:**
- Credit: `https://www.peoplesbank.lk/promotion-category/supermarkets/?cardType=credit_card`
- Debit: `https://www.peoplesbank.lk/promotion-category/supermarkets/?cardType=debit_card`
**Wait selector:** `article.offer-card`

### HTML structure
Two separate requests are made (credit and debit). Offer cards are `article.offer-card`. Inside each:
- `.promo-short` → merchant / short title
- `.merchant-name` → offer description (multi-line; only first line used; `...See more` suffix stripped)
- `.valid-date` → validity period

### Known issues
- The description class name is `.merchant-name` but it contains the offer text, not just the merchant. This is a naming quirk in People's Bank's HTML.
- Multi-line descriptions sometimes include fine-print after a newline; only the first line is kept.
- Two scrape requests are needed per run (once per card type), which doubles the load time for this bank.

---

## Adding a new bank

1. Check if the bank's offers page is server-rendered HTML or a JS SPA (use browser DevTools Network tab).
2. Identify the CSS selectors for: offer container, merchant/supermarket, offer text, validity dates.
3. Write `async def scrape_<key>(browser: Browser) -> List[Offer]` in `scraper.py`.
4. Register it in `BANKS` dict at the bottom of `scraper.py`.
5. Document the URL, wait selector, extra_wait, HTML structure, and any quirks in this file.

## Manual offers quick reference

When automated scraping fails, add entries to `backend/manual_offers.py`:

```python
Offer(
    bank="Bank Name",          # must match BANKS[key]["name"]
    supermarket="Keells",      # must match a key in SUPERMARKET_KEYWORDS
    offer_text="25% off total bill",
    card_type="Credit",        # "Credit" | "Debit" | "Credit / Debit"
    valid_from=date(2025, 6, 1),
    valid_to=date(2025, 6, 30),
    days_of_week=[0, 5, 6],    # 0=Mon … 6=Sun, empty list = every day
    source_url="https://...",
)
```

Hit **Refresh** in the UI after editing the file.
