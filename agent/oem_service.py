"""
oem_service.py - OEM parts price lookup service
"""

import asyncio
import re
from typing import Optional

import httpx

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
    "JA3":"mitsubishi","JA4":"mitsubishi","4A3":"mitsubishi",
    "MMB":"mitsubishi","MNA":"mitsubishi","MNB":"mitsubishi",
    "SAJ":"jaguar","SAL":"landrover","SAR":"landrover",
    "YV1":"volvo","YV4":"volvo",
    "MR0":"toyota","MR1":"toyota","MR2":"toyota","MR3":"toyota",
    "AAV":"toyota",
    "JS2":"suzuki","JS3":"suzuki",
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
_INTERNAL_CODE_RE = re.compile(r"^\d{12,16}$")

# FordPartsGiant price patterns.
# Each is searched independently because the page has HTML tags between them.
_FPG_MSRP_RE     = re.compile(r"MSRP:[\s\S]{0,150}?\$([\d,]+\.?\d{0,2})", re.I)
_FPG_META_RE     = re.compile(r"\$([\d,]+\.?\d{0,2})\s+online at FordPartsGiant", re.I)
_FPG_ITEMPROP_RE = re.compile(
    r"itemprop=[\"']price[\"'][^>]*content=[\"']([0-9.]+)[\"']", re.I
)

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def is_internal_audatex_code(part_number: str) -> bool:
    return bool(_INTERNAL_CODE_RE.match(part_number.strip()))


def normalize_part_number(part_number: str) -> str:
    return part_number.strip()


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


async def _fetch_fordpartsgiant(client: httpx.AsyncClient, part_number: str) -> dict:
    """
    Look up a Ford part on FordPartsGiant.com.
    Server-side HTML, no Cloudflare, no Playwright needed.
    URL: /parts/ford-part~{PN_NO_DASHES}.html  -> follows redirect to slug.
    """
    pn_clean = re.sub(r"[-\s]", "", part_number).upper()
    url = f"https://www.fordpartsgiant.com/parts/ford-part~{pn_clean}.html"
    result: dict = {"price": None, "msrp": None, "url": url, "error": None}

    try:
        print(f"    [FPG] GET {url}")
        resp = await client.get(url, follow_redirects=True, timeout=15.0)
        result["url"] = str(resp.url)

        if resp.status_code == 404:
            result["error"] = "not_found"
            print(f"    [FPG] 404 for {pn_clean}")
            return result

        if resp.status_code != 200:
            result["error"] = f"http_{resp.status_code}"
            print(f"    [FPG] HTTP {resp.status_code} for {pn_clean}")
            return result

        html = resp.text

        # MSRP: search for literal "MSRP:" followed by a price.
        # Log context around "MSRP" so we can see the actual HTML structure.
        msrp_idx = html.find("MSRP")
        if msrp_idx >= 0:
            print(f"    [FPG] MSRP context: {repr(html[msrp_idx:msrp_idx+200])}")
            m_msrp = _FPG_MSRP_RE.search(html)
            if m_msrp:
                result["msrp"] = float(m_msrp.group(1).replace(",", ""))
        else:
            print(f"    [FPG] 'MSRP' not found in HTML for {pn_clean}")

        # Sale price: cleanest source is the meta-description
        m_meta = _FPG_META_RE.search(html)
        if m_meta:
            result["price"] = float(m_meta.group(1).replace(",", ""))
        else:
            m_ip = _FPG_ITEMPROP_RE.search(html)
            if m_ip:
                result["price"] = float(m_ip.group(1))

        # Fallback: compute MSRP from "You Save: $xx.xx (xx%)" if regex missed it
        if result["price"] is not None and result["msrp"] is None:
            m_save = re.search(r"You Save:\s*\$([\d,]+\.?\d{0,2})", html, re.I)
            if m_save:
                savings = float(m_save.group(1).replace(",", ""))
                result["msrp"] = round(result["price"] + savings, 2)
                print(f"    [FPG] MSRP computed from You Save: {savings} -> msrp={result['msrp']}")

        # Temp debug: expose raw context in the result so we can see it via API
        msrp_idx2 = html.find("MSRP")
        result["_debug"] = {
            "html_len": len(html),
            "msrp_found": msrp_idx2 >= 0,
            "msrp_context": repr(html[msrp_idx2:msrp_idx2+250]) if msrp_idx2 >= 0 else None,
            "you_save_found": bool(__import__("re").search(r"You Save:", html, __import__("re").I)),
        }

        if result["price"] is not None:
            print(f"    [FPG] {pn_clean}: price=${result['price']}  MSRP=${result['msrp']}")
            return result

        result["error"] = "no_price"
        body_start = html.find("<body")
        snippet = html[body_start: body_start + 500].replace("\n", " ")[:300]
        print(f"    [FPG] no price found for {pn_clean}. snippet: {snippet}")

    except httpx.TimeoutException:
        result["error"] = "timeout"
        print(f"    [FPG] timeout for {pn_clean}")
    except Exception as e:
        result["error"] = str(e)
        print(f"    [FPG] error for {pn_clean}: {e}")

    return result


async def _lookup_ford_parts(parts: list, vin: Optional[str]) -> list[dict]:
    """Ford-specific: FordPartsGiant + eBay concurrently. No Playwright."""
    part_list = [
        (
            p.get("parte", "") if isinstance(p, dict) else str(p),
            p.get("descripcion", "") if isinstance(p, dict) else "",
        )
        for p in parts
    ]

    real: list[tuple] = []
    pre_results: list[dict] = []
    for pn, desc in part_list:
        if is_internal_audatex_code(pn):
            pre_results.append({
                "parte": pn, "descripcion": desc,
                "msrp": None, "price": None, "vin_fits": "N/A", "url": "",
                "error": "internal_audatex_code",
                "note": (
                    "This is an internal Inpart code, not an OEM part number. "
                    "Look up manually in the OEM catalog."
                ),
                "ebay": None,
            })
            print(f"  [skip] {pn} -- internal Audatex code")
        else:
            real.append((pn, desc))

    if not real:
        return pre_results

    print(f"[oem/ford] Fetching {len(real)} part(s) from FordPartsGiant + eBay concurrently")

    async with httpx.AsyncClient(headers=_HTTP_HEADERS) as client:
        fpg_tasks  = [_fetch_fordpartsgiant(client, pn) for pn, _ in real]
        ebay_tasks = [ebay_search_part(pn, desc, brand="ford") for pn, desc in real]
        fpg_results, ebay_results = await asyncio.gather(
            asyncio.gather(*fpg_tasks),
            asyncio.gather(*ebay_tasks),
        )

    results = list(pre_results)
    for (pn, desc), fpg, ebay in zip(real, fpg_results, ebay_results):
        msrp_s  = f"${fpg['msrp']}"  if fpg["msrp"]  else "-"
        price_s = f"${fpg['price']}" if fpg["price"] else "-"
        status  = fpg["error"] or f"MSRP:{msrp_s}  Price:{price_s}"
        print(f"  -> {pn}: {status}")
        results.append({
            "parte":       pn,
            "descripcion": desc,
            "msrp":        fpg["msrp"],
            "price":       fpg["price"],
            "vin_fits":    "N/A",
            "url":         fpg["url"],
            "error":       fpg["error"],
            "note":        None,
            "ebay":        ebay,
        })

    return results


async def _fetch_one(page, base_url: str, part_number: str, vin: Optional[str],
                     timeout_ms: int = 90_000) -> dict:
    """Look up a single part on oempartsonline.com via Playwright."""
    result = {"msrp": None, "price": None, "vin_fits": "N/A", "url": "", "error": None}

    vin_param  = f"&vin={vin}" if vin else ""
    search_url = f"{base_url}/search?search_str={part_number}{vin_param}"

    t0 = __import__("time").monotonic()
    try:
        print(f"    GET {search_url}")
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=12_000)
        except Exception:
            pass

        result["url"] = page.url
        t1 = __import__("time").monotonic()
        print(f"    URL after load ({t1-t0:.1f}s): {page.url}")

        # Fast Cloudflare detection -- bail in ~1.5s instead of wasting 12s
        try:
            _body = await page.locator("body").inner_text(timeout=1_500)
            _bl = _body.lower()
            if any(x in _bl for x in [
                "security verification", "you have been blocked",
                "verifies you are not a bot", "cloudflare",
            ]):
                print(f"    Cloudflare block detected -- skipping")
                result["error"] = "cloudflare_block"
                return result
        except Exception:
            pass

        if "/search" in page.url:
            try:
                pn_lower  = part_number.lower()
                pn_nodash = pn_lower.replace("-", "").replace(" ", "")
                link = page.locator(
                    f'a[href*="{pn_nodash}"], '
                    f'a[href*="{pn_lower}"], '
                    f'a[href*="{part_number.upper()}"]'
                ).first
                href = await link.get_attribute("href", timeout=12_000)
                if href:
                    target = (
                        href if href.startswith("http")
                        else base_url.rstrip("/") + href
                    )
                    print(f"    -> product page: {target}")
                    try:
                        await page.goto(target, wait_until="networkidle", timeout=10_000)
                    except Exception:
                        pass
                    result["url"] = page.url
            except Exception as nav_e:
                t2 = __import__("time").monotonic()
                print(f"    no product link ({t2-t0:.1f}s total): {type(nav_e).__name__}")
                try:
                    body_text = await page.locator("body").inner_text(timeout=2_000)
                    snippet   = body_text[:400].replace("\n", " ").strip()
                    print(f"    page text: {snippet}")
                except Exception:
                    pass

        html = await page.content()
        on_product_page = "/oem-parts/" in page.url

        if on_product_page:
            m = re.search(r"MSRP[\s\S]{0,40}\$([\d,]+\.?\d{0,2})", html, re.I)
            if m:
                result["msrp"] = float(m.group(1).replace(",", ""))

            price_selectors = [
                ".price-now", ".sale-price", ".your-price", ".dealer-price",
                '[class*="price-sale"]', '[class*="sale_price"]',
                '[class*="price--sale"]',
                ".product-price strong", ".price strong",
                "[data-price]", ".add-to-cart-price", ".buy-price",
                ".price-block .price",
            ]
            for sel in price_selectors:
                try:
                    txt = await page.locator(sel).first.inner_text(timeout=500)
                    p = parse_price(txt)
                    if p and p > 0:
                        result["price"] = p
                        break
                except Exception:
                    continue

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

            if vin:
                try:
                    body = (await page.inner_text("body")).lower()
                    if any(x in body for x in
                           ["does not fit", "not compatible", "does not match"]):
                        result["vin_fits"] = "NO"
                    elif any(x in body for x in [
                        "fits your", "compatible with your",
                        "guaranteed fit", "this part fits",
                    ]):
                        result["vin_fits"] = "YES"
                    elif vin.lower() in body:
                        result["vin_fits"] = "YES"
                except Exception:
                    pass
        elif "/oem-parts/" in page.url:
            try:
                _pt      = await page.locator("body").inner_text(timeout=1_500)
                _snippet = _pt[:300].replace("\n", " ").strip()
                print(f"    product page text: {_snippet}")
            except Exception:
                pass
        else:
            print(f"    stuck on search page -- skipping price/MSRP extraction")

    except PlaywrightTimeout:
        result["error"] = "TIMEOUT"
        print(f"    TIMEOUT after {timeout_ms // 1000}s")
    except Exception as e:
        result["error"] = str(e)
        print(f"    ERROR: {e}")

    return result


async def _fetch_with_retry(page, base_url: str, part_number: str, vin: Optional[str],
                            retries: int = 2, timeout_ms: int = 90_000) -> dict:
    """Wrap _fetch_one with retry; skip retry on permanent Cloudflare block."""
    for attempt in range(1, retries + 2):
        r = await _fetch_one(page, base_url, part_number, vin, timeout_ms)
        if r["error"] in (None, "", "cloudflare_block"):
            return r
        if attempt <= retries:
            wait = 3 * attempt
            print(f"    Retry {attempt}/{retries} in {wait}s...")
            await asyncio.sleep(wait)
    return r


async def lookup_parts(
    parts: list,
    vin: Optional[str] = None,
    brand: Optional[str] = None,
    headless: bool = True,
) -> list[dict]:
    """
    Look up OEM prices for a list of part numbers.

    parts:   list of dicts with 'parte' (and optionally 'descripcion')
             or plain strings
    vin:     17-char VIN -- determines brand and fitment
    brand:   explicit brand override (e.g. 'toyota')
    headless: run Playwright headlessly (non-Ford brands only)
    """
    effective_brand = brand or brand_from_vin(vin or "")
    base_url = OEM_URLS.get(effective_brand) if effective_brand else None

    # Ford: fast httpx path via FordPartsGiant.com
    if effective_brand == "ford":
        return await _lookup_ford_parts(parts, vin)

    # Unknown brand: eBay only
    if not base_url:
        part_list = [
            (
                p.get("parte", "") if isinstance(p, dict) else str(p),
                p.get("descripcion", "") if isinstance(p, dict) else "",
            )
            for p in parts
        ]
        wmi = vin[:3] if vin else "?"
        print(
            f"     -> unknown_brand (WMI: {wmi}) -- "
            f"querying eBay for {len(part_list)} parts concurrently..."
        )
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
                "error":       f"unknown_brand (VIN WMI: {wmi})",
                "note":        "Brand not in US OEM catalog -- eBay searched as fallback.",
                "ebay":        ebay_results[i],
            }
            for i, (pn, desc) in enumerate(part_list)
        ]

    # Other brands: Playwright on oempartsonline.com
    real_parts: list = []
    pre_results: list[dict] = []
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
                "note": (
                    "This is an internal Inpart code, not an OEM part number. "
                    "Look up manually in the OEM catalog."
                ),
            })
            print(f"  [skip] {part_number} -- internal Audatex code")
        else:
            real_parts.append(p)

    if not real_parts:
        return pre_results

    print(f"[oem] Looking up {len(real_parts)} real OEM part(s) on {base_url} (VIN: {vin})")

    results = list(pre_results)

    # Fire all eBay lookups concurrently before Playwright starts
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

    oem_scrape_results: list[tuple] = []

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
                oem_scrape_results.append((
                    "", "",
                    {"msrp": None, "price": None, "vin_fits": "N/A",
                     "url": "", "error": "empty_part_number"},
                ))
                continue

            print(f"  [{i}/{len(real_parts)}] {part_number}  {descripcion}")
            r = await _fetch_with_retry(page, base_url, part_number, vin)
            oem_scrape_results.append((part_number, descripcion, r))

        await browser.close()

    ebay_results = await asyncio.gather(*ebay_tasks)

    for (part_number, descripcion, r), ebay_result in zip(oem_scrape_results, ebay_results):
        if not part_number:
            continue

        msrp_s  = f"${r['msrp']}"  if r["msrp"]  else "-"
        price_s = f"${r['price']}" if r["price"] else "-"

        no_market = (r["error"] is None and r["msrp"] is None and r["price"] is None)
        note = (
            "Part not listed on oempartsonline.com for this brand. "
            "Likely not sold in the US market (e.g. Hilux, Fortuner, "
            "Ecuador/LatAm-spec vehicle)."
        ) if no_market else None

        status = r["error"] or (
            "NOT IN US MARKET" if no_market
            else f"MSRP:{msrp_s}  Price:{price_s}  Fits:{r['vin_fits']}"
        )
        print(f"  -> {part_number}: {status}")

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
