#!/usr/bin/env python3
"""
Masterpartes MCP Server — local edition
========================================
Calls oem_service / ebay_service / excel_writer directly in-process.
No Railway, no HTTP server, no API key required.

Credentials loaded from  workflow-pro/.env  at startup:
  EBAY_APP_ID, EBAY_CERT_ID  — eBay production keys
  (Inpart login handled by the browser bookmarklet — not needed here)
"""
import sys
import os
from pathlib import Path

# ── Repo paths ─────────────────────────────────────────────────────────────────
_REPO  = Path(__file__).resolve().parent.parent
_AGENT = _REPO / "agent"
_TOOLS = _REPO / "tools"

# Load credentials from .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO / ".env")
except ImportError:
    pass  # dotenv optional; env vars may already be set

# Make agent/ and tools/ importable
sys.path.insert(0, str(_AGENT))
sys.path.insert(0, str(_TOOLS))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Masterpartes")


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def check_health() -> dict:
    """
    Verify that local dependencies (oem_service, ebay_service) are importable
    and that the Excel workbook path exists.
    Call this first to confirm the local setup is working.
    """
    issues = []
    try:
        import oem_service  # noqa: F401
    except Exception as e:
        issues.append(f"oem_service: {e}")
    try:
        import ebay_service  # noqa: F401
    except Exception as e:
        issues.append(f"ebay_service: {e}")

    excel = _REPO / "cotizacion_bulk.xlsm"
    if not excel.exists():
        issues.append(f"Excel not found: {excel}")

    if not os.environ.get("EBAY_APP_ID"):
        issues.append("EBAY_APP_ID not set in .env")
    if not os.environ.get("EBAY_CERT_ID"):
        issues.append("EBAY_CERT_ID not set in .env")

    return {
        "status": "ok" if not issues else "degraded",
        "mode": "local",
        "issues": issues,
    }


@mcp.tool()
async def quote_parts(
    parts: list[dict],
    vin: str = "",
    brand: str = "",
) -> dict:
    """
    Look up OEM + eBay prices for a list of auto parts. Runs fully local.

    Args:
        parts:  List of part dicts, each with:
                  "parte"       (str, required) — OEM part number, e.g. "68404445AB"
                  "descripcion" (str, optional) — part description
        vin:    Vehicle VIN — identifies brand and checks fitment.
        brand:  Brand override when no VIN is available, e.g. "toyota", "ford".

    Returns:
        parts:   list of results, each containing:
                   msrp       → OEM list price (USD)
                   price      → OEM sale price (USD)
                   vin_fits   → "YES" / "NO" / "N/A"
                   url        → product URL on the OEM site
                   ebay       → {genuine_price, genuine_url,
                                  aftermarket_price, aftermarket_url}
        count:   total parts requested
        priced:  parts with at least one price found
    """
    from oem_service import lookup_parts
    results = await lookup_parts(
        parts,
        vin=vin or None,
        brand=brand or None,
    )
    priced = sum(
        1 for r in results
        if r.get("price") or (r.get("ebay") and (
            r["ebay"].get("genuine_price") or r["ebay"].get("aftermarket_price")
        ))
    )
    return {
        "parts":  results,
        "count":  len(results),
        "priced": priced,
        "vin":    vin,
        "brand":  brand,
    }


@mcp.tool()
async def get_excel_parts(vin: str = "") -> dict:
    """
    Read all part rows from the open Excel quotation file (cotizacion_bulk.xlsm).

    Args:
        vin: If provided, return only parts under quotations with this VIN.

    Returns list of parts with their current tariff/price data so Claude can
    review what's in the workbook before calling quote_parts.
    """
    from shared.excel_writer import get_all_parts
    parts = get_all_parts(vin_filter=vin or None)
    return {"parts": parts, "count": len(parts)}


@mcp.tool()
async def generate_avk_list(vin: str = "") -> dict:
    """
    Generate the AVK bulk-search parts list for European-brand quotations
    (Mercedes-Benz, BMW, Audi, VW, Volvo, etc.).

    Reads parts from Excel, filters to European VINs, strips dashes/spaces
    from OE numbers, and writes to avk_parts_list.txt in the repo root.

    Args:
        vin: Limit to a specific VIN (optional — default processes all European parts).

    Returns:
        parts_list:   List of cleaned OE numbers (one per line, ready for AVK)
        file_path:    Where the list was saved
        count:        Number of parts
    """
    from shared.excel_writer import get_all_parts
    from shared.config import is_european_vin, AVK_LIST_FILE

    all_parts = get_all_parts(vin_filter=vin or None)
    avk = []
    for p in all_parts:
        if is_european_vin(p.get("vin") or ""):
            pn = p["parte"].replace(" ", "").replace("-", "").upper()
            if pn:
                avk.append(pn)

    if avk:
        AVK_LIST_FILE.write_text("\n".join(avk), encoding="utf-8")

    return {
        "parts_list": avk,
        "file_path":  str(AVK_LIST_FILE),
        "count":      len(avk),
    }


if __name__ == "__main__":
    mcp.run()
