"""
import_avk_prices.py — Read AVK bookmarklet JSON and fill AVK columns in Excel.

Workflow:
  1. Run "Lista AVK" macro → copies part numbers to clipboard
  2. Open avkparts.lt, paste via "AVK: Fill Search" bookmarklet
  3. After results load, click "AVK: Get Prices" bookmarklet → copies JSON to clipboard
  4. Run this script (or use the VBA "Importar AVK" button):
       python tools\import_avk_prices.py --clipboard

Or provide a JSON file:
       python tools\import_avk_prices.py --file avk_results.json

JSON format from bookmarklet:
  [{"part": "34116850564", "supplier": "OEM Germany", "price_eur": 12.50}, ...]
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))

from shared.excel_writer import fill_avk_prices


def _read_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception as e:
        print(f"[avk] clipboard error: {e}")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--clipboard", action="store_true", help="Read JSON from clipboard")
    grp.add_argument("--file",      help="Path to JSON file with AVK results")
    args = ap.parse_args()

    if args.clipboard:
        raw = _read_clipboard()
        print(f"[avk] Read {len(raw)} chars from clipboard")
    else:
        raw = open(args.file, encoding="utf-8").read()
        print(f"[avk] Read from {args.file}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[avk] Invalid JSON: {e}")
        print("      Make sure you clicked 'AVK: Get Prices' and copied the result first.")
        sys.exit(1)

    if not isinstance(data, list):
        print("[avk] Expected a JSON array. Check bookmarklet output.")
        sys.exit(1)

    print(f"[avk] {len(data)} price entries to import…")
    fill_avk_prices(data)
    print("\n✓ AVK prices written to Excel (columns AH=genuine, AI=aftermarket).")


if __name__ == "__main__":
    main()
