"""
enrich_excel.py — Fill SUBPARTIDA, ARANCEL, eBay and OEM prices for
all unpriced parts in cotizacion_bulk.xlsm.

Called by the Excel macro "Enriquecer Precios":
    WScript.Shell.Run "python tools\enrich_excel.py"

Optional args:
    --vin VIN       Only enrich parts under this VIN
    --no-oem        Skip OEM price lookup (faster)
    --no-ebay       Skip eBay lookup
    --no-tariffs    Skip tariff lookup
"""
import sys, os, asyncio, argparse
sys.path.insert(0, os.path.dirname(__file__))

from shared.config import AGENT_DIR, EUROPEAN_WMIS, is_european_vin, is_european, AVK_LIST_FILE, PARTSOUQ_LIST_FILE
sys.path.insert(0, str(AGENT_DIR))

from shared.tariff_lookup import lookup
from shared.excel_writer  import get_all_parts, fill_pricing


# ── eBay lookup (reuse agent/ebay_service.py) ─────────────────────────────────

async def _ebay_lookup(parts: list[dict]) -> list[dict]:
    """Returns list of {parte, ebay: {genuine_price, genuine_url, aftermarket_price, aftermarket_url}}"""
    from ebay_service import search_part
    results = []
    for p in parts:
        print(f"  [ebay] {p['parte']}  {p['descripcion']}")
        ebay = await search_part(p["parte"], p["descripcion"], brand="")
        results.append({"parte": p["parte"], "ebay": ebay})
    return results


# ── OEM lookup (reuse agent/oem_service.py httpx scrapers) ────────────────────

async def _oem_lookup(parts: list[dict]) -> list[dict]:
    """
    OEM lookup: httpx scrapers for known US brands, Playwright for Mercedes.

    European brands that have a US parts site (Mercedes → mbpartsgiant.com;
    BMW/Audi/VW/Volvo → *PartsDeal/*PartsGiant) are always tried first —
    regardless of VIN origin.  Only European brands with NO US site
    (Renault, Fiat, MINI, etc.) are skipped here and left for AVK.
    """
    from oem_service import (
        _lookup_parts_via_httpx, _lookup_mercedes_playwright,
        brand_from_vin, brand_from_text, _PARTS_SITES, OEM_URLS,
    )

    # Group by VIN/brand
    by_vin: dict[str, list[dict]] = {}
    for p in parts:
        vin      = p.get("vin") or ""
        armadora = p.get("armadora") or ""
        brand_key = brand_from_text(armadora) or (brand_from_vin(vin) if vin else None)
        # A brand has a US site if it's Mercedes, in the httpx scrapers dict,
        # or in the oempartsonline.com dict (Porsche, Jaguar, Land Rover).
        has_us_site = brand_key and (
            brand_key == "mercedes"
            or brand_key in _PARTS_SITES
            or brand_key in OEM_URLS
        )
        if is_european(vin, armadora) and not has_us_site:
            continue  # Truly European brand with no US site — AVK handles these
        by_vin.setdefault(vin, []).append(p)

    all_results = []
    for vin, group in by_vin.items():
        # Prefer the brand as stated directly on the quote (Inpart's
        # "armadora" field) over guessing from the VIN's WMI prefix.
        armadora = next((p.get("armadora") for p in group if p.get("armadora")), None)
        brand = brand_from_text(armadora) or (brand_from_vin(vin) if vin else None)
        if brand == "mercedes":
            print(f"  [oem/mercedes] {len(group)} parts (VIN: {vin or '?'})")
            results = await _lookup_mercedes_playwright(group, vin or "", headless=True)
            all_results.extend(results)
        elif brand and brand in _PARTS_SITES:
            print(f"  [oem/{brand}] {len(group)} parts (VIN: {vin or '?'})")
            results = await _lookup_parts_via_httpx(group, vin or None, brand)
            all_results.extend(results)
        else:
            # No fast scraper for this brand
            for p in group:
                all_results.append({
                    "parte":    p["parte"],
                    "msrp":     None,
                    "price":    None,
                    "vin_fits": "N/A",
                    "url":      "",
                    "error":    "no_fast_scraper",
                })

    return all_results


# ── AVK list generator ────────────────────────────────────────────────────────

def _generate_avk_list(parts: list[dict]) -> list[str]:
    """
    Return OE numbers for European-brand parts (one per line, no spaces).
    Format required by AVK bulk search.

    Brand is taken from the quote's own armadora field first (authoritative
    -- stated directly on the quote), falling back to VIN WMI-prefix
    matching only when armadora wasn't captured. WMI lists are incomplete
    for regional-assembly plants (e.g. a VW built in Argentina/Brazil can
    carry a WMI that isn't in any hardcoded European list).
    """
    avk_parts = []
    for p in parts:
        if is_european(p.get("vin") or "", p.get("armadora") or ""):
            # Remove all spaces from OE number
            pn = p["parte"].replace(" ", "").replace("-", "").upper()
            avk_parts.append(pn)
    return avk_parts


# ── PartSouq candidate list (manual bookmarklet fallback) ────────────────────

def _generate_partsouq_list(parts: list[dict]) -> list[str]:
    """
    Return part numbers still missing an OEM price after the automated
    lookup — candidates for a manual PartSouq search via the bookmarklet
    (the httpx-based automatic PartSouq call can get Cloudflare-blocked;
    a real browser tab usually isn't).

    Skips European-VIN parts (that's AVK's job) and internal Audatex/Grupo
    Pieza codes (15+ all-digit codes — not a real manufacturer part number,
    no lookup will ever find these).
    """
    from oem_service import is_internal_audatex_code
    out = []
    for p in parts:
        if p.get("oem_precio") not in (None, ""):
            continue  # already priced
        if is_european(p.get("vin") or "", p.get("armadora") or ""):
            continue  # AVK's job
        pn = (p.get("parte") or "").strip()
        if not pn or is_internal_audatex_code(pn):
            continue
        # Strip spaces and dashes — same format as PartSouq bookmarklet expects
        pn_clean = pn.replace(" ", "").replace("-", "").upper()
        out.append(pn_clean)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vin",         default=None)
    ap.add_argument("--no-oem",      action="store_true")
    ap.add_argument("--no-ebay",     action="store_true")
    ap.add_argument("--no-tariffs",  action="store_true")
    args = ap.parse_args()

    parts = get_all_parts(vin_filter=args.vin)
    if not parts:
        print("[enrich] No parts found in Excel.")
        sys.exit(0)

    print(f"[enrich] {len(parts)} parts to enrich.")

    # ── 1. Tariff lookup ──────────────────────────────────────────────────────
    if not args.no_tariffs:
        from shared.tariff_lookup import lookup
        from shared.excel_writer import _open_wb, COL
        wb = _open_wb()
        ws = wb.sheets["COTIZACION"]
        for p in parts:
            if p["subpartida"]:
                continue  # already filled
            result = lookup(p["descripcion"])
            if result["subpartida"]:
                ws.cells(p["row"], COL["SUBPARTIDA"]).value = result["subpartida"]
                ws.cells(p["row"], COL["ARANCEL"]).value    = result["arancel"]
                print(f"  [tariff] {p['parte']}: {result['subpartida']} {result['arancel']}%")
            else:
                # Highlight missing tariff in orange (tuple, not raw int —
                # xlwings/COM is BGR-ordered so a raw int renders inverted)
                ws.cells(p["row"], COL["SUBPARTIDA"]).color = (255, 206, 118)
                print(f"  [tariff] {p['parte']}: NO MATCH — cell highlighted")
        wb.save()

    # ── 2. eBay lookup ────────────────────────────────────────────────────────
    if not args.no_ebay:
        print(f"\n[enrich] eBay lookup for {len(parts)} parts…")
        ebay_results = asyncio.run(_ebay_lookup(parts))
        fill_pricing(oem_results=[], ebay_results=ebay_results)

    # ── 3. OEM lookup (fast httpx sites) ─────────────────────────────────────
    if not args.no_oem:
        print(f"\n[enrich] OEM lookup…")
        oem_results = asyncio.run(_oem_lookup(parts))
        fill_pricing(oem_results=oem_results, ebay_results=[])

    # ── 4. AVK list ───────────────────────────────────────────────────────────
    avk = _generate_avk_list(parts)
    if avk:
        AVK_LIST_FILE.write_text("\n".join(avk), encoding="utf-8")
        print(f"\n[avk] {len(avk)} European parts -> {AVK_LIST_FILE}")
        print("      Open the AVK bookmarklet page, copy this file's content, run 'AVK: Fill Search'")
        # Also copy to clipboard
        try:
            import pyperclip
            pyperclip.copy("\n".join(avk))
            print("      (also copied to clipboard)")
        except Exception:
            pass

    # ── 5. PartSouq candidate list (manual fallback) ─────────────────────────
    # Re-read current state so this reflects what actually got priced above,
    # not the pre-lookup snapshot from the top of this function.
    parts_after = get_all_parts(vin_filter=args.vin)
    partsouq = _generate_partsouq_list(parts_after)
    if partsouq:
        PARTSOUQ_LIST_FILE.write_text("\n".join(partsouq), encoding="utf-8")
        print(f"\n[partsouq] {len(partsouq)} part(s) still unpriced -> {PARTSOUQ_LIST_FILE}")
        print("           Click 'Lista PartSouq' in Excel, then search each one on partsouq.com")
        print("           and click the PartSouq bookmarklet after each search.")

    print("\n✓ Enrichment complete.")


if __name__ == "__main__":
    main()
