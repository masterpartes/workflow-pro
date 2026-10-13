"""
setup_excel_columns.py — One-time script to add missing column headers
to cotizacion_bulk.xlsm.

Adds headers in row 2 (the header row) for columns beyond X:
  Y  = IMPORTADO
  Z  = OEM_MSRP($)
  AA = OEM_PRECIO($)
  AB = VIN_FITS
  AC = OEM_URL
  AD = EBAY_GENUINE($)
  AE = EBAY_GENUINE_URL
  AF = EBAY_AFTER($)
  AG = EBAY_AFTER_URL
  AH = AVK_GENUINE(€)
  AI = AVK_AFTER(€)

Run once:
    python tools/setup_excel_columns.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from shared.config import EXCEL_FILE
import xlwings as xw

HEADER_ROW = 2   # assumes row 1 = title, row 2 = column headers

EXTRA_COLS = [
    (25, "IMPORTADO"),
    (26, "OEM_MSRP($)"),
    (27, "OEM_PRECIO($)"),
    (28, "VIN_FITS"),
    (29, "OEM_URL"),
    (30, "EBAY_GENUINE($)"),
    (31, "EBAY_GENUINE_URL"),
    (32, "EBAY_AFTER($)"),
    (33, "EBAY_AFTER_URL"),
    (34, "AVK_GENUINE(€)"),
    (35, "AVK_AFTER(€)"),
]

# xlwings/COM wants (r, g, b) tuples — a raw 0xRRGGBB int gets sent straight
# to the BGR-ordered OLE_COLOR API and renders inverted (navy -> brown/orange).
HEADER_BG   = (31, 78, 121)     # navy
HEADER_FG   = (255, 255, 255)   # white
HEADER_BOLD = True


def main():
    wb = xw.Book(str(EXCEL_FILE))
    ws = wb.sheets["COTIZACION"]

    print(f"Adding column headers to row {HEADER_ROW} of {EXCEL_FILE.name}…")
    for col, label in EXTRA_COLS:
        cell = ws.cells(HEADER_ROW, col)
        current = cell.value
        if current and str(current).strip():
            print(f"  col {col} ({label}): already has '{current}' — skipping")
            continue
        cell.value = label
        cell.color = HEADER_BG
        cell.font.color = HEADER_FG
        cell.font.bold = HEADER_BOLD
        cell.font.size = 10
        cell.font.name = "Arial"
        cell.column_width = 16
        print(f"  col {col}: ✓ {label}")

    wb.save()
    print("\n✓ Done. Column headers updated.")


if __name__ == "__main__":
    main()
