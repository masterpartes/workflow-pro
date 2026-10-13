"""
generate_avk_list.py — Regenerate avk_parts_list.txt directly from whatever
quote is currently on the COTIZACION sheet, and copy it to the clipboard.

Why this exists: avk_parts_list.txt used to only get (re)written as a side
effect of running OEM PX ("Enriquecer Precios"). If you imported a new quote
but hadn't re-run OEM PX yet, clicking "Lista AVK" would silently hand you
the PREVIOUS quote's list — no error, just wrong part numbers with no
connection to what's actually on screen. This script always reads the live
sheet, so the "AVKO" button can never be stale.

Called by the Excel macro "MostrarListaAVK" (AVKO button), before it reads
the file and copies it to the clipboard:
    python tools\\generate_avk_list.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from shared.config import AVK_LIST_FILE, is_european
from shared.excel_writer import get_all_parts


def generate_avk_list(parts: list[dict]) -> list[str]:
    """
    Return OE numbers for European-brand parts (one per line, no spaces/dashes).
    Format required by AVK bulk search. Mirrors enrich_excel.py's
    _generate_avk_list — kept here too so this can run standalone, without
    needing OEM PX to have run first.

    Brand comes from the quote's own armadora field first (authoritative),
    falling back to VIN WMI-prefix matching only when armadora is missing.
    WMI lists are incomplete for regional-assembly plants -- e.g. a VW
    built in Argentina/Brazil can carry a WMI ("8L7...") that isn't in any
    hardcoded European list, even though the vehicle is clearly a VW.
    """
    avk_parts = []
    for p in parts:
        if is_european(p.get("vin") or "", p.get("armadora") or ""):
            pn = p["parte"].replace(" ", "").replace("-", "").upper()
            avk_parts.append(pn)
    return avk_parts


def main():
    parts = get_all_parts()
    avk = generate_avk_list(parts)

    if not avk:
        # Still write an empty file so the VBA side gets a clear "0 parts"
        # rather than silently reusing an old file with stale content.
        AVK_LIST_FILE.write_text("", encoding="utf-8")
        print("[avk] No European-brand parts found on the current quote.")
        sys.exit(0)

    AVK_LIST_FILE.write_text("\n".join(avk), encoding="utf-8")
    print(f"[avk] {len(avk)} part(s) from the current quote -> {AVK_LIST_FILE}")


if __name__ == "__main__":
    main()
