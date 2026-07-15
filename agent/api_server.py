"""
api_server.py — Masterpartes Quoting Agent API
===============================================
FastAPI cloud service deployed on Railway.

Endpoints:
  GET  /health                → liveness check
  POST /quote                 → price a list of parts (direct input or image OCR)
  POST /inpart/sync           → login to Inpart, scrape all pending quotations
  POST /inpart/quote-all      → sync + price everything (full batch, use 2x/day)

Authentication:
  All endpoints (except /health) require header:
    X-API-Key: <API_SECRET_KEY env var>

Environment variables required:
  INPART_USERNAME   — Inpart portal username
  INPART_PASSWORD   — Inpart portal password
  API_SECRET_KEY    — shared secret for API auth (set a strong random string)
"""

import asyncio
import os
import base64
import re
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from inpart_scraper import scrape_pending_quotations
from oem_service import lookup_parts, brand_from_vin

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Masterpartes Quoting Agent",
    description="Remote OEM parts pricing API for the Claude phone agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "")

# ── Auth ──────────────────────────────────────────────────────────────────────

def verify_api_key(x_api_key: str = Header(...)):
    if not API_SECRET_KEY:
        raise HTTPException(status_code=500, detail="API_SECRET_KEY env var not set")
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ── Cache for Inpart sync results ─────────────────────────────────────────────
# Simple in-memory cache — avoids scraping Inpart on every /quote-all call
_inpart_cache: dict = {"quotations": [], "updated_at": 0}
CACHE_TTL = 3600  # 1 hour


def _cache_is_fresh() -> bool:
    return (time.time() - _inpart_cache["updated_at"]) < CACHE_TTL


# ── Request / Response models ─────────────────────────────────────────────────

class Part(BaseModel):
    parte: str
    descripcion: str = ""
    cantidad: str = "1"


class QuoteRequest(BaseModel):
    parts: list[Part]
    vin: Optional[str] = None
    brand: Optional[str] = None          # explicit brand override (e.g. "toyota")


class InpartSyncRequest(BaseModel):
    days_back: int = 7
    debug: bool = False


class InpartQuoteAllRequest(BaseModel):
    days_back: int = 7
    force_resync: bool = False           # ignore cache and re-scrape Inpart
    debug: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "masterpartes-quoting-agent",
        "inpart_cache_age_s": int(time.time() - _inpart_cache["updated_at"]),
        "inpart_cache_count": len(_inpart_cache["quotations"]),
    }


@app.post("/quote", dependencies=[Depends(verify_api_key)])
async def quote(req: QuoteRequest):
    """
    Price a list of OEM parts.

    Input: parts list + VIN (or explicit brand)
    Output: same parts with msrp, price, vin_fits, url fields added

    Used for:
    - Mode 2 (image OCR): Claude extracts part numbers from photo, calls this
    - Mode 3 (direct list): user pastes a list of part numbers, Claude calls this
    """
    if not req.parts:
        raise HTTPException(status_code=400, detail="parts list is empty")

    # Build input for oem_service
    parts_input = [{"parte": p.parte, "descripcion": p.descripcion} for p in req.parts]

    try:
        results = await lookup_parts(
            parts=parts_input,
            vin=req.vin,
            brand=req.brand,
            headless=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OEM lookup failed: {e}")

    return {
        "vin":    req.vin,
        "brand":  req.brand or brand_from_vin(req.vin or ""),
        "parts":  results,
        "count":  len(results),
        "priced": sum(1 for r in results if r.get("price")),
    }


@app.post("/inpart/sync", dependencies=[Depends(verify_api_key)])
async def inpart_sync(req: InpartSyncRequest):
    """
    Login to Inpart and scrape all pending quotations.
    Returns the quotation list (parts are fetched from detail pages).
    Results are cached in memory for 1 hour.
    """
    try:
        quotations = await scrape_pending_quotations(
            days_back=req.days_back,
            fetch_details=True,
            debug=req.debug,
            headless=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inpart sync failed: {e}")

    _inpart_cache["quotations"] = quotations
    _inpart_cache["updated_at"] = time.time()

    return {
        "status":     "synced",
        "count":      len(quotations),
        "quotations": quotations,
        "cached_at":  _inpart_cache["updated_at"],
    }


@app.post("/inpart/quote-all", dependencies=[Depends(verify_api_key)])
async def inpart_quote_all(req: InpartQuoteAllRequest):
    """
    Full pipeline: sync Inpart + price all parts for all pending quotations.

    Steps:
      1. Scrape Inpart for pending quotations (or use cache)
      2. For each quotation, call OEM lookup for all parts using the VIN
      3. Return structured results ready for quoting

    This is the main endpoint called 2x/day from the Claude phone agent.
    """
    # Step 1: Get quotations
    if req.force_resync or not _cache_is_fresh():
        try:
            quotations = await scrape_pending_quotations(
                days_back=req.days_back,
                fetch_details=True,
                debug=req.debug,
                headless=True,
            )
            _inpart_cache["quotations"] = quotations
            _inpart_cache["updated_at"] = time.time()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Inpart sync failed: {e}")
    else:
        quotations = _inpart_cache["quotations"]
        print(f"[api] Using cached Inpart data ({len(quotations)} quotations)")

    # Step 2: Price all parts
    output = []

    for q in quotations:
        vin    = q.get("vin")
        parts  = q.get("partes", [])

        if not parts:
            output.append({
                **q,
                "oem_results": [],
                "priced":      0,
                "warning":     "no_parts_found",
            })
            continue

        if not vin:
            output.append({
                **q,
                "oem_results": [],
                "priced":      0,
                "warning":     "no_vin_found",
            })
            continue

        brand = brand_from_vin(vin)
        if not brand:
            output.append({
                **q,
                "oem_results": [],
                "priced":      0,
                "warning":     f"unknown_brand (WMI: {vin[:3]})",
            })
            continue

        print(f"[api] Pricing {len(parts)} parts for COT {q['cotizacion_id']} | {brand} | {vin}")

        try:
            oem_results = await lookup_parts(
                parts=parts,
                vin=vin,
                headless=True,
            )
        except Exception as e:
            oem_results = []
            print(f"[api] OEM lookup error for COT {q['cotizacion_id']}: {e}")

        output.append({
            **q,
            "oem_results": oem_results,
            "priced":      sum(1 for r in oem_results if r.get("price")),
            "total_parts": len(oem_results),
        })

    return {
        "status":      "completed",
        "quotations":  output,
        "total_priced": sum(q.get("priced", 0) for q in output),
        "total_parts":  sum(q.get("total_parts", 0) for q in output),
        "synced_from_cache": not req.force_resync and _cache_is_fresh(),
    }


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    # Validate required env vars
    missing = []
    for var in ("INPART_USERNAME", "INPART_PASSWORD", "API_SECRET_KEY"):
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        print(f"WARNING: Missing environment variables: {', '.join(missing)}")
    else:
        print("[startup] All required environment variables are set.")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=False)
