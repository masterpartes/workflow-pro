"""
import_partsouq_prices.py — Read PartSouq bookmarklet JSON and fill
OEM_PRECIO/OEM_URL in Excel.

Manual fallback path: the automated PartSouq lookup (httpx, inside OEM PX)
can get Cloudflare-blocked. A normal browser tab usually isn't, so this lets
you search each still-unpriced part manually and pull the results in.

Workflow:
  1. Run OEM PX ("Enriquecer") — any part still missing a price after that
     gets written to partsouq_parts_list.txt
  2. Click "Lista PartSouq" macro → copies that list to clipboard
  3. Open partsouq.com, paste one part number at a time into the search box
  4. After each search, click the "PartSouq: Extraer Precio" bookmarklet —
     it accumulates results across searches (persisted in the browser tab)
  5. Once done, click "Copiar JSON" in the bookmarklet's overlay
  6. Run this script (or use the VBA "Importar PartSouq" button):
       python tools\\import_partsouq_prices.py --clipboard

Or provide a JSON file:
       python tools\\import_partsouq_prices.py --file partsouq_results.json

JSON format from bookmarklet:
  [{"parte": "6407A337", "descripcion": "...", "make": "Mitsubishi",
    "price": 50.59, "url": "https://partsouq.com/..."}, ...]
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))

from shared.excel_writer import fill_partsouq_prices


def _read_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception as e:
        print(f"[partsouq] clipboard error: {e}")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--clipboard", action="store_true", help="Read JSON from clipboard")
    grp.add_argument("--file",      help="Path to JSON file with PartSouq results")
    args = ap.parse_args()

    if args.clipboard:
        raw = _read_clipboard()
        print(f"[partsouq] Read {len(raw)} chars from clipboard")
    else:
        raw = open(args.file, encoding="utf-8").read()
        print(f"[partsouq] Read from {args.file}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[partsouq] Invalid JSON: {e}")
        print("           Make sure you clicked 'Copiar JSON' in the PartSouq bookmarklet overlay first.")
        sys.exit(1)

    if not isinstance(data, list):
        print("[partsouq] Expected a JSON array. Check bookmarklet output.")
        sys.exit(1)

    if not data:
        print("[partsouq] Empty list — nothing to import.")
        sys.exit(0)

    print(f"[partsouq] {len(data)} price entries to import…")
    fill_partsouq_prices(data)
    print("\n✓ PartSouq prices written to Excel (OEM_PRECIO / OEM_URL columns).")


if __name__ == "__main__":
    main()
