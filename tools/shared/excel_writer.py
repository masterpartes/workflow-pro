"""
Excel writer — xlwings-based helpers for writing auction data and
enrichment data into cotizacion_bulk.xlsm.

Works with Excel open (xlwings talks to the running instance via COM).
"""
import xlwings as xw
from datetime import datetime
from typing import Optional
from shared.config import EXCEL_FILE

HIST_SHEET_NAME = "HISTORICO"
# Full data range per quote block: A (1) through AI (35, AVK_AFTER)
_LAST_COL = 35


# ── Column indices (1-based) ──────────────────────────────────────────────────
COL = {
    "PARTE":         1,   # A
    "DESCRIPCION":   2,   # B
    "SUBPARTIDA":    3,   # C
    "FOB":           4,   # D
    "PESO":          5,   # E
    "ARANCEL":       6,   # F
    "MARGEN":        7,   # G — formula from CONFIG
    "INSURANCE":     8,   # H — formula
    "FREIGHT":       9,   # I — formula
    "CIF":          10,   # J — formula
    "ADVALOREM":    11,   # K — formula
    "FONDINFA":     12,   # L — formula
    "IVA_ADUANA":   13,   # M — formula
    "TOTAL_ADUANA": 14,   # N — formula
    "SALIDA_DIVISAS":15,  # O — formula
    "FLETE_SIATI":  16,   # P — formula
    "FUEL_COURIER": 17,   # Q — formula
    "RAYOS_X":      18,   # R — formula
    "TRAMITE":      19,   # S — formula
    "TOTAL_SIATI":  20,   # T — formula
    "PRECIO_UIO":   21,   # U — formula
    "GANANCIA":     22,   # V — formula
    "CREDITO_IVA":  23,   # W — formula
    "PRECIO_OFERTA":24,   # X — formula
    "IMPORTADO":    25,   # Y — timestamp
    "OEM_MSRP":     26,   # Z
    "OEM_PRECIO":   27,   # AA
    "VIN_FITS":     28,   # AB
    "OEM_URL":      29,   # AC
    "EBAY_GENUINE":      30,   # AD
    "EBAY_GENUINE_URL":  31,   # AE
    "EBAY_AFTER":        32,   # AF
    "EBAY_AFTER_URL":    33,   # AG
    "AVK_GENUINE":       34,   # AH — AVK EUR genuine/OEM price
    "AVK_AFTER":         35,   # AI — AVK EUR aftermarket price
}

# NOTE: xlwings/COM expects (r, g, b) tuples here — NOT raw 0xRRGGBB ints.
# Passing a raw int gets forwarded straight to the Windows OLE_COLOR API,
# which is BGR-ordered, so e.g. 0x1F4E79 (navy) rendered as brownish-orange
# and 0x0000FF (blue) rendered as red. Tuples let xlwings do the RGB->BGR
# conversion correctly.
NAVY   = (31, 78, 121)
WHITE  = (255, 255, 255)
YELLOW = (255, 230, 153)
LIGHT_BLUE = (245, 249, 255)
ALT_ROW = (238, 244, 255)
BLUE_TEXT = (0, 70, 200)   # input-cell font color (was rendering red)
BLACK = (0, 0, 0)

FORMULAS = [
    "=IF(D{r}=\"\",\"\",0.01*D{r})",                                      # H
    "=IF(E{r}=\"\",\"\",4*E{r})",                                          # I  (freight: $4/kg)
    "=IF(D{r}=\"\",\"\",D{r}+H{r}+I{r})",                                 # J
    "=IF(J{r}=\"\",\"\",J{r}*(F{r}/100))",                                # K
    "=IF(J{r}=\"\",\"\",0.005*J{r})",                                     # L
    "=IF(J{r}=\"\",\"\",(CONFIG!$B$2/100)*(J{r}+K{r}+L{r}))",            # M
    "=IF(K{r}=\"\",\"\",K{r}+L{r}+M{r})",                                # N
    "=IF(D{r}=\"\",\"\",D{r}*(CONFIG!$B$3/100))",                        # O
    "=IF(E{r}=\"\",\"\",3.7*E{r}*(1+CONFIG!$B$2/100))",                  # P
    "=IF(P{r}=\"\",\"\",0.027*P{r})",                                     # Q
    "=IF(P{r}=\"\",\"\",0.017*P{r})",                                     # R
    "=IF(E{r}=\"\",\"\",(30/35)*E{r}*(1+CONFIG!$B$2/100))",              # S
    "=IF(P{r}=\"\",\"\",P{r}+Q{r}+R{r}+S{r})",                          # T
    "=IF(D{r}=\"\",\"\",D{r}+O{r}+N{r}+T{r})",                          # U
    "=IF(U{r}=\"\",\"\",(G{r}/100)*U{r})",                               # V
    "=IF(M{r}=\"\",\"\",M{r})",                                           # W
    "=IF(U{r}=\"\",\"\",U{r}+V{r}-W{r})",                               # X
]


def _open_wb() -> xw.Book:
    """Open or attach to the workbook."""
    try:
        return xw.Book(str(EXCEL_FILE))
    except Exception:
        return xw.Book(str(EXCEL_FILE))


def _find_last_data_row(ws: xw.Sheet) -> int:
    """Last row with data in column A."""
    return ws.cells(ws.cells.last_cell.row, 1).end("up").row


def _write_header_row(ws: xw.Sheet, row: int, text: str):
    """Write a navy auction header row (merged A:AC)."""
    # Write text and merge
    ws.range(ws.cells(row, 1), ws.cells(row, 25)).merge()
    cell = ws.cells(row, 1)
    cell.value = text
    cell.font.bold = True
    cell.font.size = 10
    cell.font.color = WHITE
    cell.color = NAVY
    cell.row_height = 20



def _write_part_row(ws: xw.Sheet, row: int, parte: str, descripcion: str, alt: bool,
                    subpartida: str = None, arancel: float = None):
    """Write a part row with inputs + formulas."""
    parte_cell = ws.cells(row, COL["PARTE"])
    # Force text format BEFORE assigning — otherwise Excel auto-converts
    # long all-digit part numbers (Grupo Pieza internal codes) into a
    # number and displays them in scientific notation (e.g. 2.60709E+14).
    parte_cell.number_format = "@"
    parte_cell.value = parte
    ws.cells(row, COL["DESCRIPCION"]).value = descripcion
    if subpartida:
        ws.cells(row, COL["SUBPARTIDA"]).value = subpartida
    if arancel is not None:
        ws.cells(row, COL["ARANCEL"]).value = arancel

    # MARGEN formula
    ws.cells(row, COL["MARGEN"]).formula = "=CONFIG!$B$4"

    # Formulas H→X (columns 8→24)
    for i, fml in enumerate(FORMULAS):
        ws.cells(row, 8 + i).formula = fml.replace("{r}", str(row))
        ws.cells(row, 8 + i).number_format = "#,##0.00"

    # Styling
    bg = ALT_ROW if alt else WHITE
    for col in range(1, 8):
        c = ws.cells(row, col)
        c.color = bg
        c.font.size = 10
        c.font.color = BLUE_TEXT if col <= 3 else BLACK

    # PRECIO_OFERTA highlight (col X = 24)
    ws.cells(row, 24).color = YELLOW
    ws.cells(row, 24).font.bold = True

    ws.cells(row, COL["VIN_FITS"]).value = "N/A"
    ws.api.Rows(row).RowHeight = 18


def _get_or_create_history_sheet(wb: xw.Book) -> xw.Sheet:
    """Get the HISTORICO sheet, creating it (with the same title/column-header
    rows as COTIZACION) if it doesn't exist yet."""
    for sh in wb.sheets:
        if sh.name == HIST_SHEET_NAME:
            return sh
    src = wb.sheets["COTIZACION"]
    hist = wb.sheets.add(HIST_SHEET_NAME, after=src)
    # Copy the title + column-header rows so HISTORICO reads the same way
    src.range((1, 1), (2, _LAST_COL)).copy(hist.range((1, 1)))
    return hist


def _archive_existing_quotes(ws: xw.Sheet, wb: xw.Book):
    """
    Move whatever quote block(s) currently sit in COTIZACION (rows 3..last)
    to HISTORICO, then wipe them from COTIZACION.

    COTIZACION is meant to hold only the quote currently being priced — old
    quotes are kept for reference in HISTORICO instead of piling up (and
    getting silently re-scraped/re-priced) on the live sheet.
    """
    last = _find_last_data_row(ws)
    if last <= 2:
        return  # nothing to archive

    hist = _get_or_create_history_sheet(wb)
    hist_last = _find_last_data_row(hist)
    dest_start = hist_last + 2 if hist_last > 2 else 3

    if hist_last > 2:
        hist.api.Rows(hist_last + 1).RowHeight = 8  # blank separator row

    n_rows = last - 2  # rows 3..last
    src_range = ws.range((3, 1), (last, _LAST_COL))
    dest_range = hist.range((dest_start, 1), (dest_start + n_rows - 1, _LAST_COL))
    src_range.copy(dest_range)

    # Freeze formulas into static values so the archived record reflects what
    # was actually priced at the time — not whatever CONFIG! rates are live
    # the next time someone opens the workbook.
    dest_range.value = dest_range.value

    # Clear the archived rows from COTIZACION (contents + formatting) so the
    # next import starts on a clean sheet.
    ws.range((3, 1), (last, _LAST_COL)).clear()
    print(f"[excel] Archived {n_rows} row(s) to {HIST_SHEET_NAME} (rows {dest_start}-{dest_start + n_rows - 1})")


def write_quotation(quotation: dict, subpartidas: list[dict] = None, archive_previous: bool = True):
    """
    Write one quotation (header + parts) to the Excel sheet.

    quotation: output from inpart_scraper (cotizacion_id, siniestro, aseguradora,
               matricula, ano_modelo, vin, taller, partes)
    subpartidas: list of {subpartida, arancel} per part (same order as partes)
    archive_previous: if True (default), any quote already sitting in
        COTIZACION is moved to HISTORICO first, so this quote starts fresh
        at row 3. Pass False to append instead of archiving (rare).
    """
    wb = _open_wb()
    ws = wb.sheets["COTIZACION"]

    if archive_previous:
        _archive_existing_quotes(ws, wb)

    last = _find_last_data_row(ws)
    start = last + 2 if last > 2 else 3  # blank separator row above

    # Separator row
    if last > 2:
        ws.api.Rows(last + 1).RowHeight = 8

    # Header text
    q = quotation
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
    header = (
        f"COT. {q.get('cotizacion_id','')}  |  "
        f"{q.get('siniestro','')}  |  "
        f"{q.get('aseguradora','')}  |  "
        f"{q.get('armadora','')}  |  "
        f"{q.get('matricula','')} ({q.get('ano_modelo','')})  |  "
        f"{q.get('vin','')}  |  "
        f"{q.get('taller','')}  |  "
        f"{ts}"
    )
    _write_header_row(ws, start, header)

    # Part rows
    partes = q.get("partes", [])
    for i, parte in enumerate(partes):
        r = start + 1 + i
        sp = (subpartidas[i] if subpartidas and i < len(subpartidas) else {})
        _write_part_row(
            ws, r,
            parte.get("parte", ""),
            parte.get("descripcion", ""),
            alt=(i % 2 == 1),
            subpartida=sp.get("subpartida"),
            arancel=sp.get("arancel"),
        )

    wb.save()
    print(f"[excel] COT {q.get('cotizacion_id')} written: {len(partes)} parts starting at row {start}")
    return start, start + len(partes)


def fill_pricing(oem_results: list[dict], ebay_results: list[dict]):
    """
    Fill OEM + eBay pricing columns for existing part rows.
    Matches by PARTE value in column A.

    oem_results : [{parte, msrp, price, vin_fits, url, error}]
    ebay_results: [{parte, ebay: {genuine: {price_min, ...}, all: {price_min, ...}, url, ...}}]
                  — this is the raw dict returned by agent/ebay_service.py's search_part().
    """
    wb = _open_wb()
    ws = wb.sheets["COTIZACION"]

    # Build index: parte → row number
    idx: dict[str, int] = {}
    last = _find_last_data_row(ws)
    for r in range(3, last + 1):
        pn = ws.cells(r, 1).value
        if pn and isinstance(pn, str) and not pn.startswith("COT."):
            idx[pn.strip().upper()] = r

    def set_cell(row, col, val):
        if val is not None:
            ws.cells(row, col).value = val

    for res in (oem_results or []):
        pn = str(res.get("parte", "")).strip().upper()
        r = idx.get(pn)
        if not r:
            continue
        set_cell(r, COL["OEM_MSRP"],    res.get("msrp"))
        set_cell(r, COL["OEM_PRECIO"],  res.get("price"))
        set_cell(r, COL["VIN_FITS"],    res.get("vin_fits", "N/A"))
        set_cell(r, COL["OEM_URL"],     res.get("url"))

    for res in (ebay_results or []):
        pn = str(res.get("parte", "")).strip().upper()
        r = idx.get(pn)
        if not r:
            continue
        ebay = res.get("ebay") or {}
        if isinstance(ebay, dict):
            # ebay_service.search_part() returns nested "genuine"/"aftermarket"
            # buckets (each {count, price_min, total_min}), not flat
            # genuine_price/aftermarket_price keys — reading the wrong keys
            # here silently left EBAY_GENUINE/EBAY_AFTER blank on every run.
            #
            # Use total_min (item price + cheapest shipping to our zip), not
            # price_min — shipping is often a large fraction of these parts'
            # cost and price_min alone understates the real landed cost.
            genuine     = ebay.get("genuine") or {}
            aftermarket = ebay.get("aftermarket") or {}
            ebay_url    = ebay.get("url")
            set_cell(r, COL["EBAY_GENUINE"],     genuine.get("total_min"))
            set_cell(r, COL["EBAY_GENUINE_URL"], ebay_url)
            set_cell(r, COL["EBAY_AFTER"],       aftermarket.get("total_min"))
            set_cell(r, COL["EBAY_AFTER_URL"],   ebay_url)

    wb.save()
    print(f"[excel] Pricing filled for {len(oem_results or []) + len(ebay_results or [])} part(s)")


def fill_avk_prices(avk_results: list[dict]):
    """
    Fill AVK prices from bookmarklet JSON results.

    avk_results: list of {part, supplier, price_eur}
                 (JSON output from the AVK: Get Prices bookmarklet)

    Groups by part number, picks lowest genuine (OEM) and lowest aftermarket price.
    Supplier names with 'OEM' or brand name → genuine; otherwise → aftermarket.
    """
    wb = _open_wb()
    ws = wb.sheets["COTIZACION"]

    last = _find_last_data_row(ws)
    idx: dict[str, int] = {}
    for r in range(3, last + 1):
        pn = ws.cells(r, 1).value
        if pn and isinstance(pn, str) and not pn.startswith("COT."):
            idx[pn.strip().upper().replace(" ", "").replace("-", "")] = r

    # Group: part → {genuine: [prices], after: [prices]}
    grouped: dict[str, dict] = {}
    for item in avk_results:
        pn = str(item.get("part", "")).strip().upper().replace(" ", "").replace("-", "")
        supplier = str(item.get("supplier", "")).upper()
        price = item.get("price_eur")
        if not pn or price is None:
            continue
        g = grouped.setdefault(pn, {"genuine": [], "after": []})
        # Heuristic: explicit OEM/ORIGINAL/GENUINE wording, OR a manufacturer-
        # group supplier code (AVK's own vehicle-maker groupings, e.g. "PSA E"/
        # "PSA T" for Peugeot-Citroën-DS, "FCA I"/"FCA T1" for Fiat-Chrysler-
        # Jeep-Alfa) -- these ARE the genuine part, just sourced from a
        # different dealer/warehouse within the manufacturer's own network.
        # Everything else (TYC, DEPOT, AYFAR, L-SERIES, VALEO, etc.) is a
        # third-party aftermarket brand.
        _GENUINE_GROUP_PREFIXES = ("PSA", "FCA", "OPEL/PSA", "VAG", "BMW", "MERCEDES", "MB ", "VOLVO", "JLR")
        is_oem = (
            any(kw in supplier for kw in ("OEM", "ORIGINAL", "GENUINE"))
            or any(supplier.startswith(p) for p in _GENUINE_GROUP_PREFIXES)
        )
        if is_oem:
            g["genuine"].append(float(price))
        else:
            g["after"].append(float(price))

    filled = 0
    for pn, prices in grouped.items():
        r = idx.get(pn)
        if not r:
            continue
        if prices["genuine"]:
            ws.cells(r, COL["AVK_GENUINE"]).value = min(prices["genuine"])
        if prices["after"]:
            ws.cells(r, COL["AVK_AFTER"]).value = min(prices["after"])
        filled += 1

    wb.save()
    print(f"[excel] AVK prices filled for {filled} part(s)")


def get_all_parts(vin_filter: str = None) -> list[dict]:
    """
    Read all part rows from the sheet.
    Returns [{row, parte, descripcion, subpartida, arancel, vin}]
    vin_filter: if given, only return parts under auctions with this VIN.
    """
    wb = _open_wb()
    ws = wb.sheets["COTIZACION"]
    last = _find_last_data_row(ws)

    import re

    parts = []
    current_vin = None
    current_armadora = None
    for r in range(3, last + 1):
        v = ws.cells(r, 1).value
        if v is None:
            continue
        v = str(v)
        if v.startswith("COT."):
            # Extract VIN from header text (17-char sequence)
            m = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", v, re.I)
            current_vin = m.group(0) if m else None
            # armadora (vehicle manufacturer) is the 4th "|"-delimited
            # segment: COT.id | siniestro | aseguradora | armadora | ...
            # More reliable than guessing brand from the VIN's WMI prefix,
            # since Inpart states the manufacturer directly.
            segs = [s.strip() for s in v.split("|")]
            current_armadora = segs[3] if len(segs) > 3 and segs[3] else None
            continue
        if vin_filter and current_vin != vin_filter:
            continue
        parts.append({
            "row":          r,
            "parte":        v.strip(),
            "descripcion":  str(ws.cells(r, COL["DESCRIPCION"]).value or ""),
            "subpartida":   ws.cells(r, COL["SUBPARTIDA"]).value,
            "arancel":      ws.cells(r, COL["ARANCEL"]).value,
            "vin":          current_vin,
            "armadora":     current_armadora,
            "oem_precio":   ws.cells(r, COL["OEM_PRECIO"]).value,
        })

    return parts


def fill_partsouq_prices(results: list[dict]):
    """
    Fill OEM_PRECIO/OEM_URL (and PESO, when known) from the PartSouq
    bookmarklet's accumulated JSON (manual fallback for parts the automated
    PartSouq httpx call couldn't reach — usually a Cloudflare block).

    results: list of {parte, descripcion, make, price, url, weight_kg?}
             (JSON output from the PartSouq bookmarklet's "Copiar JSON")

    Matches by part number (spaces/dashes stripped, case-insensitive).
    Picks the lowest price per part if the same part appears more than once
    (e.g. searched twice, or the search returned several candidate matches).
    OEM_MSRP is intentionally left untouched — PartSouq doesn't publish MSRP.
    PESO (column E) is only filled if the cell is currently blank — never
    overwrites a weight that came from another source (e.g. Inpart).
    """
    wb = _open_wb()
    ws = wb.sheets["COTIZACION"]

    last = _find_last_data_row(ws)
    idx: dict[str, int] = {}
    for r in range(3, last + 1):
        pn = ws.cells(r, 1).value
        if pn and isinstance(pn, str) and not pn.startswith("COT."):
            idx[pn.strip().upper().replace(" ", "").replace("-", "")] = r

    grouped: dict[str, dict] = {}
    for item in results:
        pn = str(item.get("parte", "")).strip().upper().replace(" ", "").replace("-", "")
        price = item.get("price")
        if not pn or price is None:
            continue
        best = grouped.get(pn)
        if best is None or float(price) < best["price"]:
            grouped[pn] = {
                "price": float(price),
                "url": item.get("url", ""),
                "weight_kg": item.get("weight_kg"),
            }

    filled = 0
    weighed = 0
    for pn, info in grouped.items():
        r = idx.get(pn)
        if not r:
            continue
        ws.cells(r, COL["OEM_PRECIO"]).value = info["price"]
        if info["url"]:
            ws.cells(r, COL["OEM_URL"]).value = info["url"]
        if info.get("weight_kg") not in (None, ""):
            peso_cell = ws.cells(r, COL["PESO"])
            if peso_cell.value in (None, ""):
                peso_cell.value = float(info["weight_kg"])
                weighed += 1
        filled += 1

    wb.save()
    print(f"[excel] PartSouq prices filled for {filled} part(s), weight filled for {weighed}")
