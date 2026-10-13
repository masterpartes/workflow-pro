"""
scrape_inpart.py — Scrape Inpart pending quotations → write to Excel.

Called by the Excel macro "Importar Inpart" via:
    WScript.Shell.Run "python tools/scrape_inpart.py"

Reads credentials from .env (next to cotizacion_bulk.xlsm).
Writes directly to cotizacion_bulk.xlsm via xlwings (Excel can stay open).

Optional args:
    --days N        Look back N days (default 7)
    --no-tariffs    Skip Supabase tariff lookup
    --no-enrich     Skip eBay / OEM pricing
"""
import sys, os, asyncio, json, argparse
sys.path.insert(0, os.path.dirname(__file__))

from shared.config import (
    INPART_USERNAME, INPART_PASSWORD,
    EXCEL_FILE, AGENT_DIR
)
sys.path.insert(0, str(AGENT_DIR))

from shared.tariff_lookup import lookup_batch
from shared.excel_writer  import write_quotation


def _check_env():
    errors = []
    if not INPART_USERNAME:
        errors.append("INPART_USERNAME not set in .env")
    if not INPART_PASSWORD:
        errors.append("INPART_PASSWORD not set in .env")
    if errors:
        print("[ERROR] " + "\n        ".join(errors))
        print(f"\n  Add them to: {EXCEL_FILE.parent / '.env'}")
        sys.exit(1)


async def _scrape(days: int, debug: bool) -> list[dict]:
    """Run the existing inpart_scraper async pipeline."""
    from inpart_scraper import scrape_pending_quotations
    os.environ["INPART_USERNAME"] = INPART_USERNAME
    os.environ["INPART_PASSWORD"] = INPART_PASSWORD
    return await scrape_pending_quotations(
        days_back=days,
        fetch_details=True,
        debug=debug,
        headless=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days",       type=int, default=7)
    ap.add_argument("--no-tariffs", action="store_true")
    ap.add_argument("--no-enrich",  action="store_true")
    ap.add_argument("--debug",      action="store_true")
    args = ap.parse_args()

    _check_env()

    print(f"[inpart] Scraping last {args.days} day(s) of pending quotations…")
    quotations = asyncio.run(_scrape(args.days, args.debug))

    if not quotations:
        print("[inpart] No pending quotations found.")
        sys.exit(0)

    print(f"[inpart] Found {len(quotations)} quotation(s).")

    total_parts = 0
    for q in quotations:
        partes = q.get("partes", [])
        if not partes:
            print(f"  COT {q['cotizacion_id']}: no parts — skipping")
            continue

        # Tariff lookup
        subpartidas = []
        if not args.no_tariffs:
            print(f"  COT {q['cotizacion_id']}: looking up {len(partes)} tariffs…")
            descs = [p.get("descripcion", "") for p in partes]
            subpartidas = lookup_batch(descs)
        else:
            subpartidas = [{"subpartida": None, "arancel": None}] * len(partes)

        write_quotation(q, subpartidas)
        total_parts += len(partes)

        print(f"  COT {q['cotizacion_id']} ✓  ({len(partes)} parts)")

    print(f"\n✓ Done: {len(quotations)} cotizacion(es), {total_parts} part(s) written to Excel.")

    if not args.no_enrich:
        print("\nRun enrich_excel.py to fill eBay + OEM prices.")


if __name__ == "__main__":
    main()
