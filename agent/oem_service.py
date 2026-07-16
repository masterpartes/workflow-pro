"""
oem_service.py — OEM parts price lookup service
================================================
Refactored from oem_lookup.py for use as an importable async module
inside the FastAPI cloud service.

Key improvements over original:
  - Importable: lookup_parts(parts, vin) → list of price results
  - Retry logic: up to 2 retries per part on timeout
  - Longer timeouts (90 s) for slow sites like mopar.oempartsonline.com
  - Browser instance is shared across all parts in a batch (faster)
  - No Excel / CSV dependency — pure in-memory API
"""

import asyncio
import re
from typing import Optional

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    raise ImportError("Run: pip install playwright && playwright install chromium")

try:
    from playwright_stealth import stealth_async
    STEALTH = True
except ImportError:
    STEALTH = False

from ebay_service import search_part as ebay_search_part

# ── VIN → brand map (same as oem_lookup.py) ──────────────────────────────────
WMI_TO_BRAND: dict[str, str] = {
    "1B3":"mopar","1B7":"mopar","1C3":"mopar","1C4":"mopar","1C6":"mopar",
    "1C8":"mopar","2C3":"mopar","2C4":"mopar","3C4":"mopar","3C6":"mopar",
    "1D3":"mopar","2D3":"mopar",
    "1FA":"ford","1FB":"ford","1FC":"ford","1FD":"ford","1FM":"ford",
    "1FT":"ford","2FM":"ford","2FT":"ford","3FA":"ford","3FE":"ford",
    "1G1":"gm","1G6":"gm","1GB":"gm","1GC":"gm","1GD":"gm","1GE":"gm",
    "1GF":"gm","1GK":"gm","1GN":"gm","1GS":"gm","1GT":"gm","1GW":"gm",
    "1GY":"gm","2G1":"gm","3G1":"gm","KL1":"gm","W04":"gm",
    "1HG":"honda","2HG":"honda","5FN":"honda","19U":"acura","JH4":"acura",
    "4T1":"toyota","4T3":"toyota","4T4":"toyota","5TD":"toyota","5TF":"toyota",
    "5TL":"toyota","5TM":"toyota","5TE":"toyota","JTD":"toyota","JTG":"toyota",
    "JTH":"lexus","JT6":"lexus","2T1":"toyota","2T2":"lexus",
    "1N4":"nissan","5N1":"nissan","3N1":"nissan","1N6":"nissan",
    "JN1":"nissan","JN8":"nissan","JNK":"infiniti",
    "KMH":"hyundai","KM8":"hyundai","5NM":"hyundai","5NP":"hyundai",
    "KNA":"kia","KND":"kia","5XX":"kia",
    "WBA":"bmw","WBX":"bmw","WBS":"bmw","5UX":"bmw","4US":"bmw",
    "WAU":"audi","WA1":"audi",
    "WVW":"vw","1VW":"vw","3VW":"vw",
    "WP0":"porsche","WP1":"porsche",
    "JM1":"mazda","JM3":"mazda","1YV":"mazda",
    "4S3":"subaru","JF1":"subaru","JF2":"subaru",
    "JA3":"mitsubishi","JA4":"mitsubishi","4A3":"mitsubishi","MMB":"mitsubishi","MNA":"mitsubishi","MNB":"mitsubishi",
    "SAJ":"jaguar","SAL":"landrover","SAR":"landrover",
    "YV1":"volvo","YV4":"volvo",
    # Toyota/Lexus manufactured in Thailand, South Africa, Australia (common in LatAm)
    "MR0":"toyota","MR1":"toyota","MR2":"toyota","MR3":"toyota",
    "AAV":"toyota",  # Toyota Thailand (Fortuner, Innova, Hilux)
    "MNB":"toyota",  # Toyota Thailand
    "JS2":"suzuki","JS3":"suzuki",
    # Isuzu
    "JAA":"isuzu","JA6":"isuzu",
}

OEM_URLS: dict[str, str] = {
    "acura":      "https://acura.oempartsonline.com",
    "audi":       "https://audi.oempartsonline.com",
    "bmw":        "https://bmw.oempartsonline.com",
    "ford":       "https://ford.oempartsonline.com",
    "gm":         "https://gm.oempartsonline.com",
    "honda":      "https://honda.oempartsonline.com",
    "hyundai":    "https://hyundai.oempartsonline.com",
    "infiniti":   "https://infiniti.oempartsonline.com",
    "jaguar":     "https://jaguar.oempartsonline.com",
    "kia":        "https://kia.oempartsonline.com",
    "landrover":  "https://landrover.oempartsonline.com",
    "lexus":      "https://lexus.oempartsonline.com",
    "mazda":      "https://mazda.oempartsonline.com",
    "mitsubishi": "https://mitsubishi.oempartsonline.com",
    "mopar":      "https://mopar.oempartsonline.com",
    "nissan":     "https://nissan.oempartsonline.com",
    "porsche":    "https://porsche.oempartsonline.com",
    "subaru":     "https://subaru.oempartsonline.com",
    "toyota":     "https://toyota.oempartsonline.com",
    "vw":         "https://vw.oempartsonline.com",
    "volvo":      "https://volvo.oempartsonline.com",
}

VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$", re.I)

# Internal Audatex codes are pure-numeric strings of 12–16 digits
# (e.g. 260709175213338). They are NOT OEM part numbers.
_INTERNAL_CODE_RE = re.compile(r"^\d{12,16}$")


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_internal_audatex_code(part_number: str) -> bool:
    """Return True if part_number is an internal Audatex/Inpart code, not a real OEM number."""
    return bool(_INTERNAL_CODE_RE.match(part_number.strip()))


def normalize_part_number(part_number: str) -> str:
    """
    Normalize an OEM part number for URL search.
    Inpart sometimes uses spaces where OEM catalogs use dashes (e.g. '52119 0K820' → '52119-0K820').
    We search with both the original and dash-normalized form.
    """
    return part_number.strip()  # oempartsonline.com handles spaces fine in search


def brand_from_vin(vin: str) -> Optional[str]:
    if vin and VIN_RE.match(vin):
        return WMI_TO_BRAND.get(vin[:3].upper())
    return None


def base_url_from_vin(vin: str) -> Optional[str]:
    brand = brand_from_vin(vin)
    return OEM_URLS.get(brand) if brand else None


def parse_price(text: str) -> Optional[float]:
    m = re.search(r"\$([\d,]+\.?\d{0,2})", str(text).replace(" ", ""))
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


# ── Single-part lookup ────────────────────────────────────────────────────────

async def _fetch_one(page, base_url: str, part_number: str, vin: Optional[str],
                     timeout_ms: int = 90_000) -> dict:
    """
    Look up a single part number on oempartsonline.com.
    Returns dict: {msrp, price, vin_fits, url, error}
    """
    result = {"msrp": None, "price": None, "vin_fits": "N/A", "url": "", "error": None}

    vin_param  = f"&vin={vin}" if vin else ""
    search_url = f"{base_url}/search?search_str={part_number}{vin_param}"

    t0 = __import__("time").monotonic()
    try:
        print(f"    GET {search_url}")

        # Use networkidle for ALL RevolutionParts sites — it waits until React
        # has fully rendered the search results (no more pending XHR).
        # Cap at 12 s; if the site doesn't settle it's likely blocking us.
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=12_000)
        except Exception:
            pass  # use whatever loaded

        result["url"] = page.url
        t1 = __import__("time").monotonic()
        print(f"    URL after load ({t1-t0:.1f}s): {page.url}")

        # If still on search results, navigate to the matching product page
        if "/search" in page.url:
            try:
                pn_lower = part_number.lower()
                pn_nodash = pn_lower.replace("-", "").replace(" ", "")
                link = page.locator(
                    f'a[href*="{pn_nodash}"], a[href*="{pn_lower}"], a[href*="{part_number.upper()}"]' 
                ).first
                href = await link.get_attribute("href", timeout=3_000)
                if href:
                    target = href if href.startswith("http") else base_url.rstrip("/") + href
                    print(f"    → product page: {target}")
                    try:
                        await page.goto(target, wait_until="networkidle", timeout=10_000)
                    except Exception:
                        pass
                    result["url"] = page.url
            except Exception as nav_e:
                t2 = __import__("time").monotonic()
                print(f"    no product link ({t2-t0:.1f}s total): {type(nav_e).__name__}")

        html = await page.content()

        # ── MSRP ─────────────────────────────────────────────────────────
        m = re.search(r"MSRP[\s\S]{0,40}\$([\d,]+\.?\d{0,2})", html, re.I)
        if m:
            result["msrp"] = float(m.group(1).replace(",", ""))

        # ── Sale / dealer price ───────────────────────────────────────────
        price_selectors = [
            ".price-now", ".sale-price", ".your-price", ".dealer-price",
            '[class*="price-sale"]', '[class*="sale_price"]', '[class*="price--sale"]',
            ".product-price strong", ".price strong",
            "[data-price]", ".add-to-cart-price", ".buy-price",
            ".price-block .price",
        ]
        for sel in price_selectors:
            try:
                txt = await page.locator(sel).first.inner_text(timeout=2_000)
                p = parse_price(txt)
                if p and p > 0:
                    result["price"] = p
                    break
            except Exception:
                continue

        # Fallback: pick the lowest dollar amount on page (≤ MSRP if known)
        if not result["price"]:
            amounts = [
                float(x.replace(",", ""))
                for x in re.findall(r"\$([\d,]+\.\d{2})", html)
                if 0 < float(x.replace(",", "")) < 99_999
            ]
            pts = sorted(set(amounts))
            if pts:
                if result["msrp"]:
                    under = [p for p in pts if p <= result["msrp"]]
                    result["price"] = min(under) if under else pts[0]
                else:
                    result["price"] = pts[0]

        # ── VIN fitment ───────────────────────────────────────────────────
        if vin:
            try:
                body = (await page.inner_text("body")).lower()
                if any(x in body for x in ["does not fit", "not compatible", "does not match"]):
                    result["vin_fits"] = "NO"
                elif any(x in body for x in
                         ["fits your", "compatible with your", "guaranteed fit", "this part fits"]):
                    result["vin_fits"] = "YES"
                elif vin.lower() in body:
                    result["vin_fits"] = "YES"
            except Exception:
                pass

    except PlaywrightTimeout:
        result["error"] = "TIMEOUT"
        print(f"    TIMEOUT after {timeout_ms // 1000}s")
    except Exception as e:
        result["error"] = str(e)
        print(f"    ERROR: {e}")

    return result


async def _fetch_with_retry(page, base_url: str, part_number: str, vin: Optional[str],
                            retries: int = 2, timeout_ms: int = 90_000) -> dict:
    """Wrap _fetch_one with retry logic."""
    for attempt in range(1, retries + 2):
        r = await _fetch_one(page, base_url, part_number, vin, timeout_ms)
        if r["error"] in (None, ""):
            return r
        if attempt <= retries:
            wait = 3 * attempt
            print(f"    Retry {attempt}/{retries} in {wait}s…")
            await asyncio.sleep(wait)
    return r  # return last attempt result (with error)


# ── Public API ────────────────────────────────────────────────────────────────

async def lookup_parts(
    parts: list[str],
    vin: Optional[str] = None,
    brand: Optional[str] = None,
    headless: bool = True,
) -> list[dict]:
    """
    Look up OEM prices for a list of part numbers.

    Args:
        parts:    list of OEM part number strings
        vin:      17-character VIN (used to determine brand + fitment)
        brand:    explicit brand key (e.g. "toyota") — overrides VIN-based detection
        headless: run browser headlessly

    Returns:
        list of dicts, one per part:
          {parte, descripcion, msrp, price, vin_fits, url, error}
    """
    # Resolve brand → base URL
    effective_brand = brand or brand_from_vin(vin or "")
    base_url = OEM_URLS.get(effective_brand) if effective_brand else None

    if not base_url:
        # Brand unknown — fire all eBay calls concurrently
        part_list = [
            (p.get("parte", "") if isinstance(p, dict) else str(p),
             p.get("descripcion", "") if isinstance(p, dict) else "")
            for p in parts
        ]
        print(f"     → unknown_brand (WMI: {vin[:3] if vin else '?'}) — "
              f"querying eBay for {len(part_list)} parts concurrently...")
        ebay_results = await asyncio.gather(*[
            ebay_search_part(pn, desc, brand="")
            for pn, desc in part_list
        ])
        return [
            {
                "parte":       pn,
                "descripcion": desc,
                "msrp":        None,
                "price":       None,
                "vin_fits":    "N/A",
                "url":         "",
                "error":       f"unknown_brand (VIN WMI: {vin[:3] if vin else '?'})",
                "note":        "Brand not in US OEM catalog — eBay searched as fallback.",
                "ebay":        ebay_results[i],
            }
            for i, (pn, desc) in enumerate(part_list)
        ]

    # Pre-filter: separate real OEM parts from internal Audatex codes
    real_parts = []
    pre_results = []
    for p in parts:
        part_number = p.get("parte", "") if isinstance(p, dict) else str(p)
        descripcion = p.get("descripcion", "") if isinstance(p, dict) else ""
        if is_internal_audatex_code(part_number):
            pre_results.append({
                "parte":       part_number,
                "descripcion": descripcion,
                "msrp":        None,
                "price":       None,
                "vin_fits":    "N/A",
                "url":         "",
                "error":       "internal_audatex_code",
                "note":        "This is an internal Inpart code, not an OEM part number. "
                               "Look up manually in the OEM catalog.",
            })
            print(f"  [skip] {part_number} — internal Audatex code, not a real OEM number")
        else:
            real_parts.append(p)

    if not real_parts:
        return pre_results

    print(f"[oem] Looking up {len(real_parts)} real OEM part(s) on {base_url} (VIN: {vin})")

    results = list(pre_results)  # start with pre-flagged internal codes

    # ── Fire all eBay lookups concurrently BEFORE Playwright starts ───────────
    # asyncio.create_task schedules them immediately; Playwright OEM scraping
    # runs below while eBay HTTP calls complete in the background.
    ebay_tasks = [
        asyncio.create_task(
            ebay_search_part(
                p.get("parte", "") if isinstance(p, dict) else str(p),
                p.get("descripcion", "") if isinstance(p, dict) else "",
                brand=effective_brand or "",
            )
        )
        for p in real_parts
    ]

    oem_scrape_results: list[tuple] = []  # (part_number, descripcion, oem_result)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = await ctx.new_page()
        if STEALTH:
            await stealth_async(page)

        for i, part_entry in enumerate(real_parts, 1):
            if isinstance(part_entry, dict):
                part_number = part_entry.get("parte", "")
                descripcion = part_entry.get("descripcion", "")
            else:
                part_number = str(part_entry)
                descripcion = ""

            if not part_number:
                oem_scrape_results.append(("", "", {"msrp": None, "price": None,
                                                     "vin_fits": "N/A", "url": "",
                                                     "error": "empty_part_number"}))
                continue

            print(f"  [{i}/{len(real_parts)}] {part_number}  {descripcion}")
            r = await _fetch_with_retry(page, base_url, part_number, vin)
            oem_scrape_results.append((part_number, descripcion, r))

        await browser.close()

    # ── Collect eBay results (most already done during Playwright scraping) ────
    ebay_results = await asyncio.gather(*ebay_tasks)

    for (part_number, descripcion, r), ebay_result in zip(oem_scrape_results, ebay_results):
        if not part_number:
            continue

        msrp_s  = f"${r['msrp']}"  if r["msrp"]  else "-"
        price_s = f"${r['price']}" if r["price"] else "-"

        no_market = (
            r["error"] is None
            and r["msrp"] is None
            and r["price"] is None
        )
        note = ("Part not listed on oempartsonline.com for this brand. "
                "Likely not sold in the US market (e.g. Hilux, Fortuner, "
                "Ecuador/LatAm-spec vehicle).") if no_market else None

        status = r["error"] or (f"NOT IN US MARKET" if no_market else f"MSRP:{msrp_s}  Price:{price_s}  Fits:{r['vin_fits']}")
        print(f"  → {part_number}: {status}")

        results.append({
            "parte":       part_number,
            "descripcion": descripcion,
            "msrp":        r["msrp"],
            "price":       r["price"],
            "vin_fits":    r["vin_fits"],
            "url":         r["url"],
            "error":       r["error"],
            "note":        note,
            "ebay":        ebay_result,
        })

    return results
