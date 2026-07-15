"""
ebay_service.py - eBay Browse API price lookup for auto parts
Required env vars: EBAY_APP_ID, EBAY_CERT_ID

Filters: New condition only, Buy It Now only, shipping to Miami FL 33195
Results split into: genuine / aftermarket / all
"""

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

_GENUINE_WORDS = {
    "genuine", "oem", "original equipment", "factory oem", "dealer oem",
    # Brand-specific OEM names
    "mopar", "motorcraft", "acdelco", "ac delco",
}
_AFTERMARKET_WORDS = {
    "aftermarket", "replacement", "compatible", "direct fit",
    "premium quality", "high quality", "new replacement",
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
    if not items_data:
        return {"count": 0, "price_min": None, "price_max": None,
                "price_avg": None, "ship_min": None}
    prices    = [p for p, _ in items_data]
    shippings = [s for _, s in items_data if s is not None]
    totals    = [p + (s if s is not None else 0) for p, s in items_data]
    return {
        "count":     len(prices),
        "price_min": round(min(prices), 2),
        "price_max": round(max(prices), 2),
        "price_avg": round(sum(prices) / len(prices), 2),
        "ship_min":  round(min(shippings), 2) if shippings else None,
        "total_min": round(min(totals), 2),   # lowest (price + shipping to Miami)
    }


async def search_part(part_number: str, descripcion: str = "") -> dict:
    """
    Search eBay for a part number (new + Buy It Now + ships to Miami FL 33195).
    Returns price stats split by genuine vs aftermarket.
    """
    _empty = {"count": 0, "price_min": None, "price_max": None,
              "price_avg": None, "ship_min": None}
    result = {
        "found": False, "listing_count": 0,
        "genuine": dict(_empty), "aftermarket": dict(_empty), "all": dict(_empty),
        "currency": "USD", "url": "", "error": None,
    }

    token = await _get_access_token()
    if not token:
        result["error"] = "no_credentials"
        return result

    query = part_number.strip()
    if descripcion:
        extra = " ".join(descripcion.split()[:3])
        query = f"{query} {extra}"

    result["url"] = (
        "https://www.ebay.com/sch/6028/i.html"
        + "?_nkw=" + part_number.replace(" ", "+")
        + "&LH_BIN=1&LH_ItemCondition=1000&LH_Shipped_to=US"
    )

    enduserctx = (
        "contextualLocation=country%3D" + SHIPPING_COUNTRY
        + "%2Czip%3D" + SHIPPING_ZIP
    )

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                EBAY_BROWSE_URL,
                params={
                    "q":            query,
                    "category_ids": AUTO_PARTS_CATEGORY,
                    "limit":        "50",
                    "filter":       "conditionIds:{1000},buyingOptions:{FIXED_PRICE}",
                },
                headers={
                    "Authorization":           f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                    "X-EBAY-C-ENDUSERCTX":     enduserctx,
                    "Content-Type":             "application/json",
                },
            )

        if resp.status_code == 200:
            data  = resp.json()
            items = data.get("itemSummaries", [])
            total = data.get("total", 0)
            if items:
                genuine_data, aftermarket_data, all_data = [], [], []
                for item in items:
                    try:
                        price = float(item.get("price", {}).get("value", 0))
                    except (ValueError, TypeError):
                        continue
                    ship  = _shipping_cost(item)
                    label = _classify(item.get("title", ""))
                    all_data.append((price, ship))
                    if label == "genuine":
                        genuine_data.append((price, ship))
                    elif label == "aftermarket":
                        aftermarket_data.append((price, ship))
                if all_data:
                    result.update({
                        "found": True, "listing_count": total,
                        "genuine":     _bucket_stats(genuine_data),
                        "aftermarket": _bucket_stats(aftermarket_data),
                        "all":         _bucket_stats(all_data),
                        "currency":    items[0].get("price", {}).get("currency", "USD"),
                    })
                    g, a = result["genuine"], result["aftermarket"]
                    print(f"[ebay] {part_number}: {total} listings | "
                          f"genuine={g['count']} avg=${g['price_avg']} | "
                          f"aftermarket={a['count']} avg=${a['price_avg']}")
            else:
                print(f"[ebay] {part_number}: no Buy-It-Now new listings found")

        elif resp.status_code == 401:
            _token_cache["access_token"] = None
            _token_cache["expires_at"]   = 0
            result["error"] = "token_expired"
        else:
            result["error"] = f"http_{resp.status_code}"
            print(f"[ebay] {part_number}: HTTP {resp.status_code} — {resp.text[:200]}")

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
