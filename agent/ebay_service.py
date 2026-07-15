"""
ebay_service.py - eBay Browse API price lookup for auto parts
=============================================================
Uses OAuth2 Client Credentials (no user login needed) to search
eBay for a part number and return price range + listing count.

Required env vars:
  EBAY_APP_ID   - Production App ID / Client ID
  EBAY_CERT_ID  - Production Cert ID / Client Secret
"""

import hashlib
import hmac
import json
import os
import time
from typing import Optional

import httpx

# ── Constants ─────────────────────────────────────────────────────────────────

EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# eBay category IDs relevant to auto parts
# 6028 = Car & Truck Parts & Accessories
# 33637 = Other Car & Truck Parts (fallback)
AUTO_PARTS_CATEGORY = "6028"

# Simple in-process token cache
_token_cache: dict = {"access_token": None, "expires_at": 0}


# ── OAuth2 ────────────────────────────────────────────────────────────────────

async def _get_access_token() -> Optional[str]:
    """Get a valid OAuth2 client credentials token, using cache if still valid."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    app_id = os.environ.get("EBAY_APP_ID")
    cert_id = os.environ.get("EBAY_CERT_ID")

    if not app_id or not cert_id:
        print("[ebay] EBAY_APP_ID or EBAY_CERT_ID not set — skipping eBay lookup")
        return None

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            EBAY_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            auth=(app_id, cert_id),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        print(f"[ebay] Token error {resp.status_code}: {resp.text[:200]}")
        return None

    data = resp.json()
    _token_cache["access_token"] = data.get("access_token")
    _token_cache["expires_at"] = now + data.get("expires_in", 7200)
    return _token_cache["access_token"]


# ── Part number search ────────────────────────────────────────────────────────

async def search_part(part_number: str, descripcion: str = "") -> dict:
    """
    Search eBay for a part number.

    Returns:
        {
          "found":        bool,
          "listing_count": int,
          "price_min":    float | None,
          "price_max":    float | None,
          "price_avg":    float | None,
          "currency":     str,
          "url":          str,          # eBay search results URL
          "error":        str | None,
        }
    """
    result = {
        "found": False,
        "listing_count": 0,
        "price_min": None,
        "price_max": None,
        "price_avg": None,
        "currency": "USD",
        "url": "",
        "error": None,
    }

    token = await _get_access_token()
    if not token:
        result["error"] = "no_credentials"
        return result

    # Build search query: part number + description words for relevance
    query = part_number.strip()
    if descripcion:
        # Add first 3 words of description to narrow results
        extra = " ".join(descripcion.split()[:3])
        query = f"{query} {extra}"

    search_url = (
        f"{EBAY_BROWSE_URL}"
        f"?q={httpx.URL(query)}"
        f"&category_ids={AUTO_PARTS_CATEGORY}"
        f"&limit=50"
        f"&fieldgroups=MATCHING_ITEMS"
    )

    result["url"] = (
        f"https://www.ebay.com/sch/6028/i.html"
        f"?_nkw={part_number.replace(' ', '+')}"
        f"&LH_ItemCondition=3000"  # New condition
    )

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                EBAY_BROWSE_URL,
                params={
                    "q": query,
                    "category_ids": AUTO_PARTS_CATEGORY,
                    "limit": "50",
                    "filter": "conditionIds:{1000|1500|2000|2500|3000}",  # New & like-new
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("itemSummaries", [])
            total = data.get("total", 0)

            if items:
                prices = []
                for item in items:
                    price_obj = item.get("price", {})
                    try:
                        prices.append(float(price_obj.get("value", 0)))
                    except (ValueError, TypeError):
                        pass

                if prices:
                    result["found"] = True
                    result["listing_count"] = total
                    result["price_min"] = round(min(prices), 2)
                    result["price_max"] = round(max(prices), 2)
                    result["price_avg"] = round(sum(prices) / len(prices), 2)
                    result["currency"] = items[0].get("price", {}).get("currency", "USD")
                    print(
                        f"[ebay] {part_number}: {total} listings, "
                        f"${result['price_min']}–${result['price_max']} avg ${result['price_avg']}"
                    )
            else:
                print(f"[ebay] {part_number}: no listings found")

        elif resp.status_code == 401:
            # Token expired mid-request; clear cache
            _token_cache["access_token"] = None
            _token_cache["expires_at"] = 0
            result["error"] = "token_expired"
            print(f"[ebay] Token expired for {part_number}")
        else:
            result["error"] = f"http_{resp.status_code}"
            print(f"[ebay] {part_number}: HTTP {resp.status_code} — {resp.text[:200]}")

    except httpx.TimeoutException:
        result["error"] = "timeout"
        print(f"[ebay] {part_number}: timeout")
    except Exception as e:
        result["error"] = str(e)
        print(f"[ebay] {part_number}: {e}")

    return result


# ── Marketplace deletion webhook helpers ──────────────────────────────────────

def compute_deletion_challenge_response(challenge_code: str, verification_token: str, endpoint: str) -> str:
    """
    Compute the challengeResponse hash required by eBay's marketplace
    account deletion notification endpoint verification.

    Hash = SHA-256( challengeCode + verificationToken + endpoint )
    """
    m = hashlib.sha256()
    m.update(challenge_code.encode())
    m.update(verification_token.encode())
    m.update(endpoint.encode())
    return m.hexdigest()
