"""
generate_partsouq_list.py — Regenerate partsouq_parts_list.txt directly from
whatever quote is currently on the COTIZACION sheet.

Same staleness problem as generate_avk_list.py: partsouq_parts_list.txt used
to only get (re)written as a side effect of running OEM PX. If a new quote
was imported but OEM PX hadn't been re-run yet, "Lista PartSouq" would hand
you the PREVIOUS quote's unpriced-parts list. This always reads the live
sheet instead.

Called by the Excel macro "MostrarListaPartSouq" (PSQO button), before it
reads the file and copies it to the clipboard:
    python tools\\generate_partsouq_list.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from shared.config import PARTSOUQ_LIST_FILE, is_european
from shared.excel_writer import get_all_parts

AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent")
sys.path.insert(0, AGENT_DIR)


def generate_partsouq_list(parts: list[dict]) -> list[str]:
    """
    Return part numbers still missing an OEM price — candidates for a manual
    PartSouq search via the batch bookmarklet. Mirrors enrich_excel.py's
    _generate_partsouq_list — kept here too so this can run standalone,
    reflecting the sheet as it is right now rather than as of the last
    OEM PX run.

    Skips European-VIN parts (that's AVK's job) and internal Audatex/Grupo
    Pieza codes (15+ all-digit codes — not a real manufacturer part number).
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
        # Strip spaces and dashes — PartSouq searches by compact part number
        # (same as AVK list). "205 620 01 98" → "2056200198".
        pn_clean = pn.replace(" ", "").replace("-", "").upper()
        out.append(pn_clean)
    return out


def main():
    parts = get_all_parts()
    partsouq = generate_partsouq_list(parts)

    if not partsouq:
        PARTSOUQ_LIST_FILE.write_text("", encoding="utf-8")
        print("[partsouq] No unpriced non-European parts found on the current quote.")
        sys.exit(0)

    PARTSOUQ_LIST_FILE.write_text("\n".join(partsouq), encoding="utf-8")
    print(f"[partsouq] {len(partsouq)} unpriced part(s) from the current quote -> {PARTSOUQ_LIST_FILE}")


if __name__ == "__main__":
    main()
