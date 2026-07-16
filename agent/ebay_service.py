"""
ebay_service.py - eBay Browse API price lookup for auto parts
Required env vars: EBAY_APP_ID, EBAY_CERT_ID

Filters: New condition only, Buy It Now only, shipping to Miami FL 33195
Results split into: genuine / aftermarket / all
"""

import asyncio
import hashlib
import os
import time
from typing import Optional

import httpx

EBAY_TOKEN_URL  = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
AUTO_PARTS_CATEGORY = "6028"
SHIPPING_ZIP     = "33195"
SHIPPING_COUNTRY = "US"

_token_cache: dict = {"access_token": None, "expires_at": 0}

# Title-keyword sets kept for backward compat but not used in search_part anymore.
# Genuine pricing now comes from brand-filtered eBay calls (GENUINE_BRAND_FILTER).
_GENUINE_WORDS = {
    "genuine", "oem", "original equipment", "factory oem", "dealer oem",
    "mopar", "motorcraft", "acdelco", "ac delco",
}
_AFTERMARKET_WORDS = {
    "aftermarket", "replacement", "compatible", "direct fit",
    "premium quality", "high quality", "new replacement",
}

# eBay Brand aspect values for genuine OEM filter.
# Used as aspect_filter=Brand:{value} (colon must NOT be URL-encoded — see genuine call).
GENUINE_BRAND_FILTER: dict[str, str] = {
    "ford":       "Ford",
    "gm":         "ACDelco",
    "mopar":      "Mopar",
    "toyota":     "Toyota",
    "honda":      "Honda",
    "nissan":     "Nissan",
    "infiniti":   "Infiniti",
    "hyundai":    "Hyundai",
    "kia":        "Kia",
    "bmw":        "BMW",
    "audi":       "Audi",
    "vw":         "Volkswagen",
    "subaru":     "Subaru",
    "mazda":      "Mazda",
    "lexus":      "Lexus",
    "acura":      "Acura",
    "mitsubishi": "Mitsubishi",
    "jaguar":     "Jaguar",
    "landrover":  "Land Rover",
    "porsche":    "Porsche",
    "volvo":      "Volvo",
    "isuzu":      "Isuzu",
    "suzuki":     "Suzuki",
}


async def _get_access_token() -> Optional[str]:
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]
    app_id  = os.environ.get("EBAY_APP_ID")
    cert_id = os.environ.get("EBAY_CERT_ID")
    if not app_id or not cert_id:
        print("[ebay] EBAY_APP_ID or EBAY_CERT_ID not set")
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            EBAY_TOKEN_URL,
            data={"grant_type": "client_credentials",
                  "scope": "https://api.ebay.com/oauth/api_scope"},
            auth=(app_id, cert_id),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        print(f"[ebay] Token error {resp.status_code}: {resp.text[:200]}")
        return None
    data = resp.json()
    _token_cache["access_token"] = data.get("access_token")
    _token_cache["expires_at"]   = now + data.get("expires_in", 7200)
    return _token_cache["access_token"]


def _classify(title: str) -> str:
    t = title.lower()
    if any(kw in t for kw in _GENUINE_WORDS):
        return "genuine"
    if any(kw in t for kw in _AFTERMARKET_WORDS):
        return "aftermarket"
    return "unknown"


def _shipping_cost(item: dict) -> Optional[float]:
    costs = []
    for opt in item.get("shippingOptions", []):
        try:
            costs.append(float(opt.get("shippingCost", {}).get("value", 0)))
        except (ValueError, TypeError):
            pass
    return round(min(costs), 2) if costs else None


def _bucket_stats(items_data: list) -> dict:
    """Return cheapest price/total from a list of (price, shipping) tuples."""
    if not items_data:
        return {"count": 0, "price_min": None, "total_min": None}
    prices = [p for p, _ in items_data]
    totals = [p + (s if s is not None else 0) for p, s in items_data]
    return {
        "count":     len(prices),
        "price_min": round(min(prices), 2),
        "total_min": round(min(totals), 2),
    }


async def search_part(part_number: str, descripcion: str = "", brand: str = "") -> dict:
    """
    Search eBay for a part number (new + Buy It Now + ships to Miami FL 33195).
    Makes two concurrent calls: all listings + brand-filtered genuine (when brand known).
    Returns cheapest prices only — no averages needed.
    """
    _empty = {"count": 0, "price_min": None, "total_min": None}
    result = {
        "found": False, "listing_count": 0,
        "genuine": dict(_empty), "all": dict(_empty),
        "currency": "USD", "url": "", "error": None,
    }

    token = await _get_access_token()
    if not token:
        result["error"] = "no_credentials"
        return result

    query = part_number.strip()
    genuine_brand = GENUINE_BRAND_FILTER.get(brand.lower()) if brand else None

    result["url"] = (
        "https://www.ebay.com/sch/6028/i.html"
        + "?_nkw=" + part_number.replace(" ", "+")
        + "&LH_BIN=1&LH_ItemCondition=1000&LH_Shipped_to=US"
    )

    enduserctx = (
        "contextualLocation=country%3D" + SHIPPING_COUNTRY
        + "%2Czip%3D" + SHIPPING_ZIP
    )
    headers = {
        "Authorization":           f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        "X-EBAY-C-ENDUSERCTX":     enduserctx,
        "Content-Type":             "application/json",
    }
    base_params = {
        "q":            query,
        "category_ids": AUTO_PARTS_CATEGORY,
        "limit":        "5",   # top 5 by relevance; we take min price from these
        # No sort= → eBay default best-match/relevance sort.
        # sort=price returns clips/gaskets at $3.99 that list the assembly part
        # number as a compatibility note.  Relevance surfaces the actual part.
        "filter":       "conditionIds:{1000},buyingOptions:{FIXED_PRICE}",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Fire primary call + optional brand-filtered genuine call concurrently
            calls = [client.get(EBAY_BROWSE_URL, params=base_params, headers=headers)]
            if genuine_brand:
                # aspect_filter=Brand:Ford must have a raw (unencoded) colon.
                # httpx URL-encodes colons in param values (%3A), which eBay
                # silently ignores. Build the URL manually to keep it raw.
                import urllib.parse as _up
                _base_qs = _up.urlencode(base_params)
                g_url = f"{EBAY_BROWSE_URL}?{_base_qs}&aspect_filter=Brand:{genuine_brand}"
                calls.append(client.get(g_url, headers=headers))
            responses = await asyncio.gather(*calls, return_exceptions=True)

        # ── primary (all listings) ────────────────────────────────────────
        resp = responses[0]
        if isinstance(resp, Exception):
            result["error"] = str(resp)
        elif resp.status_code == 200:
            data  = resp.json()
            items = data.get("itemSummaries", [])
            total = data.get("total", 0)
            if items:
                ps = []
                for it in items:
                    try:
                        ps.append((float(it["price"]["value"]), _shipping_cost(it)))
                    except (KeyError, ValueError, TypeError):
                        continue
                if ps:
                    result.update({
                        "found": True, "listing_count": total,
                        "all": _bucket_stats(ps),
                        "currency": items[0].get("price", {}).get("currency", "USD"),
                    })
            else:
                print(f"[ebay] {part_number}: no Buy-It-Now new listings found")
        elif resp.status_code == 401:
            _token_cache["access_token"] = None
            _token_cache["expires_at"]   = 0
            result["error"] = "token_expired"
        else:
            result["error"] = f"http_{resp.status_code}"
            print(f"[ebay] {part_number}: HTTP {resp.status_code} — {resp.text[:200]}")

        # ── genuine (brand-filtered) ──────────────────────────────────────
        if len(responses) > 1:
            resp2 = responses[1]
            if isinstance(resp2, Exception):
                print(f"[ebay-genuine] {part_number}: call failed — {resp2}")
            elif resp2.status_code == 200:
                g_data = resp2.json()
                g_items = g_data.get("itemSummaries", [])
                g_total = g_data.get("total", 0)
                print(f"[ebay-genuine] {part_number}: Brand:{genuine_brand} → {g_total} listings")
                if g_items:
                    gps = []
                    for it in g_items:
                        try:
                            gps.append((float(it["price"]["value"]), _shipping_cost(it)))
                        except (KeyError, ValueError, TypeError):
                            continue
                    if gps:
                        result["genuine"] = _bucket_stats(gps)
            else:
                print(f"[ebay-genuine] {part_number}: HTTP {resp2.status_code}")

        g = result["genuine"]; a = result["all"]
        print(f"[ebay] {part_number}: total={result['listing_count']} | "
              f"all_min=${a['price_min']} | genuine_min=${g['price_min']}")

    except httpx.TimeoutException:
        result["error"] = "timeout"
    except Exception as e:
        result["error"] = str(e)

    return result


def compute_deletion_challenge_response(
    challenge_code: str, verification_token: str, endpoint: str
) -> str:
    m = hashlib.sha256()
    m.update(challenge_code.encode())
    m.update(verification_token.encode())
    m.update(endpoint.encode())
    return m.hexdigest()
