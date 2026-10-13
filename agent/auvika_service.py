"""
auvika_service.py – AVK Parts (avkparts.lt) OEM price lookup via Supabase.

The `auvika_prices` table is pre-loaded from the AVK pricing CSV and contains:
  oe TEXT, price_eur NUMERIC(10,2), manufacturer TEXT, source TEXT

Environment variables required on Railway:
  SUPABASE_URL      https://hysmhkmqaijlglplckxq.supabase.co
  SUPABASE_ANON_KEY eyJ...
"""

import os
import re
from typing import Optional
import httpx

SUPABASE_URL      = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
TABLE             = "auvika_prices"

_NORM_RE = re.compile(r"[\s\-\.\/ ]")


def _normalize_oe(oe: str) -> str:
    """Strip spaces, dashes, dots, slashes; uppercase."""
    return _NORM_RE.sub("", oe).upper()


async def lookup_auvika_price(oe: str) -> Optional[dict]:
    """
    Query Supabase for an OE number.

    Returns:
        {"price_eur": float, "manufacturer": str} if found, else None.

    Tries exact match first, then normalized (no-dash) match.
    Returns None when SUPABASE_URL / SUPABASE_ANON_KEY are not set.
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None

    oe = oe.strip()
    if not oe:
        return None

    headers = {
        "apikey":        SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Accept":        "application/json",
    }

    # Try up to two variants: raw OE, then normalized
    candidates = [oe]
    norm = _normalize_oe(oe)
    if norm != oe:
        candidates.append(norm)

    async with httpx.AsyncClient(headers=headers, timeout=5.0) as client:
        for candidate in candidates:
            try:
                resp = await client.get(
                    f"{SUPABASE_URL}/rest/v1/{TABLE}",
                    params={
                        "oe":     f"eq.{candidate}",
                        "select": "price_eur,manufacturer",
                        "limit":  "1",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        row = data[0]
                        return {
                            "price_eur":    float(row["price_eur"]),
                            "manufacturer": row.get("manufacturer", ""),
                        }
            except Exception:
                return None  # Don't let AVK errors break the main lookup

    return None
