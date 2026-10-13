# Masterpartes — System Reference

## cotizacion_bulk.xlsm — Buttons

| Button | What it does |
|--------|-------------|
| **INPART** | Reads JSON from clipboard (put there by the Inpart bookmarklet) and writes the quotation header + parts to the COTIZACION sheet. Before writing, archives whatever quote is currently on COTIZACION to HISTORICO (see below) so the sheet always starts fresh. |
| **MANUAL** | Lets you feed a list of parts and a VIN manually (no bookmarklet needed). Same archive-then-write behavior as INPART. |
| **OEM PX** | Runs the full price lookup (OEM scraper + eBay) and fills the pricing columns in Excel — only for the current quote on COTIZACION. Also writes `partsouq_parts_list.txt` for any part still unpriced afterward. |
| **AVKO** | Regenerates the European-brand part list straight from whatever quote is currently on COTIZACION (`tools/generate_avk_list.py`), then copies it to clipboard — no spaces, one part per line — ready to paste into the AVK/Auvika bulk search |
| **AVKI** | Reads the AVK/Auvika results page, collects genuine and aftermarket prices, and writes them to the AVK columns in Excel |
| **Lista PartSouq** | Regenerates the still-unpriced-parts list straight from the current quote (`tools/generate_partsouq_list.py`), then copies it to clipboard, ready for the PartSouq batch bookmarklet |
| **Importar PartSouq** | Reads the PartSouq bookmarklet's accumulated JSON from clipboard and writes prices into OEM_PRECIO/OEM_URL |

Not yet wired to a button (needs to be added manually in Excel — see below): **Lista PartSouq** and **Importar PartSouq** exist as VBA macros (`MostrarListaPartSouq`, `ImportarPreciosPartSouq`) but need shape buttons drawn and assigned, same as the existing ones (`Insertar > Formas > Rectángulo > Clic derecho > Asignar macro`). The macros were added to `ImportarCotizacion.bas` — re-import that module (`Alt+F11 > Archivo > Importar archivo...`) to get them into the live workbook.

---

## PartSouq Manual Fallback (bookmarklet, v3 — batch automatic)

Why this exists: the automated PartSouq lookup inside OEM PX (`agent/oem_service.py`, httpx-based) can get Cloudflare-blocked. A normal browser tab reliably isn't — verified live, partsouq.com resolves cleanly with no challenge page. `partsouq_bookmarklet.html` — drag the blue button to your bookmarks bar, use on partsouq.com (any page, no login needed).

**v3 processes the whole list in one click** (no more searching part-by-part). Click the bookmarklet once; it reads the part list from the clipboard (same list "Lista PartSouq" copies in Excel — falls back to a paste prompt if clipboard access is denied), then for each part number, sequentially:
1. Fetches the search results page (`fetch`, same-origin) and checks for a `.product-v2-card` — if none, marks the part "no encontrado" and moves on (this pre-check is why the site's own "no results" alert dialog never fires and never blocks the loop).
2. If found, loads that part's page in a hidden same-origin `<iframe>` (this hydrates the site's real JS/cart logic, unlike a bare `fetch`, which only returns static server HTML).
3. Clears any existing cart contents inside that iframe (`a.mini-cart-remove-button` hrefs via `fetch`), clicks the real "Add" button, and waits for the "Shipping $X" line to appear — this measures **standalone per-part shipping** (isolated cart, not cumulative — matches how parts actually get awarded/ordered independently).
4. Records `{parte, descripcion, make, item_price, shipping, price: item_price+shipping, url}` into `localStorage`, replacing any prior entry for that same part number.

A small overlay top-right shows live progress ("Procesando 4/12: ..."), a running found/not-found count, and "Copiar JSON" / "Limpiar" buttons — same as before, just no longer needs a click after every single part.

Flow: OEM PX → "Lista PartSouq" (copies still-unpriced part numbers to clipboard) → open partsouq.com → click the bookmarklet once, wait for it to finish the whole list → "Copiar JSON" in the overlay → "Importar PartSouq" in Excel.

⚠ The bookmarklet empties the PartSouq cart on every part it measures (required for isolation) — don't use that cart for real purchases while running a batch.

Scraper selectors (verified against the live site — v4, July 2026 redesign): `.search-product-card` per result (was `.product-v2-card`), `h1.part-col-list-h4` for description (unchanged), `.search-product-card-info-item` label/value pairs for make and weight (was text regex), `.search-product-price` for item price (was text regex), `form.js-ajax-add-to-cart button[type="submit"]` to add to cart (unchanged for in-stock parts), `Shipping[\s\t]*([\d.]+)\$` on `body.innerText` for shipping (unchanged). Out-of-stock parts (no `form.js-ajax-add-to-cart`) return item price with shipping=0 and `note:"sin stock"`.

---

## HISTORICO Sheet — Archived Quotes

COTIZACION is meant to hold only the quote currently being priced. Every time INPART/MANUAL writes a new quote (`write_quotation()` in `tools/shared/excel_writer.py`), it first archives whatever's already on COTIZACION (rows 3 down) into a HISTORICO sheet (created automatically on first use, same column layout), then clears COTIZACION so the new quote starts at row 3.

Archived rows have their formulas frozen to static values at the moment of archiving — so historical pricing reflects what was actually quoted at the time, not whatever CONFIG! rates (arancel/margen/insurance) happen to be set to later.

This also means OEM PX / eBay lookups only ever touch the live quote on COTIZACION — old quotes in HISTORICO are never re-scraped.

To opt out for a one-off script call (rare), pass `archive_previous=False` to `write_quotation()`.

---

## COTIZACION Sheet — Column Map

| Col | Letter | Field |
|-----|--------|-------|
| 1 | A | PARTE (OEM part number) |
| 2 | B | DESCRIPCION |
| 3 | C | SUBPARTIDA (tariff code) |
| 4 | D | FOB ($) |
| 5 | E | PESO (kg) |
| 6 | F | ARANCEL (%) |
| 7 | G | MARGEN (%) |
| 8–24 | H–X | Calculated columns (insurance, freight, CIF, duties, PRECIO_UIO, PRECIO_OFERTA) |
| 25 | Y | IMPORTADO (timestamp) |
| 26 | Z | OEM_MSRP |
| 27 | AA | OEM_PRECIO |
| 28 | AB | VIN_FITS |
| 29 | AC | OEM_URL |
| 30 | AD | EBAY_GENUINE |
| 31 | AE | EBAY_GENUINE_URL |
| 32 | AF | EBAY_AFTER |
| 33 | AG | EBAY_AFTER_URL |
| 34 | AH | AVK_GENUINE |
| 35 | AI | AVK_AFTER |

**Header row** (navy, merged A:Y):
`COT. {id}  |  {siniestro}  |  {aseguradora}  |  {matricula} ({ano_modelo})  |  {vin}  |  {taller}  |  {timestamp}`

---

## Inpart Bookmarklet (v10)

File: `inpart_bookmarklet.html` — drag the blue button to the Chrome bookmarks bar.

- Reads header fields immediately (works if you already visited "Datos Cotización" this session). If empty, clicks **Datos Cotización** and polls up to **15s** for the AJAX panel to load (verified live: can take 7+ seconds on a slow load — an earlier 6s timeout was cutting this off early and shipping a mostly-blank header). Same fallback for **Items Cotización** (10s).
- Also captures **armadora** (vehicle manufacturer, e.g. "NISSAN") — written into the header row and used by OEM PX to pick the brand directly instead of guessing from the VIN's WMI prefix (see below).
- Reads **PartNumber** (column 3 in Inpart table) — not the internal Part Serial Number
- Copies JSON to clipboard → click **INPART** in Excel to import

---

## OEM Price Lookup (OEM PX button)

`agent/oem_service.py` — httpx scraper, no browser needed.

**Brand detection:** prefers the quote's own **armadora** field (vehicle manufacturer, e.g. "NISSAN" — captured by the Inpart bookmarklet, stored as the 4th segment of the header row) over guessing from the VIN's WMI prefix. Falls back to VIN-based detection (`brand_from_vin`) only if armadora is missing or doesn't match a known brand. This matters because WMI-prefix mapping can be wrong or incomplete for regional-assembly/non-US-market VINs, while the quote states the manufacturer directly. See `brand_from_text()` / `_BRAND_ALIASES` in `oem_service.py`.

**URL patterns:**
- Most brands: `{base_url}/parts/{prefix}-part~{PN_NO_DASHES}.html`
- Mercedes-Benz: `https://www.mbpartsgiant.com/genuine/mercedes-benz~part~{PN_NO_DASHES}` (slug ignored, site auto-resolves)

**Supported brands:** mercedes, ford, mopar, gm, toyota, honda, nissan, bmw, audi, vw, volvo, lexus, mitsubishi

**European VINs** (WDB, WDD, NW1, WBA, WAU, WVW, YV1, etc.) skip OEM scraper → go to AVK instead.

**Internal code filter:** part numbers with 15+ digits (Grupo Pieza codes like `260716...`) are skipped automatically.

**PartSouq fallback:** if a part isn't found on its brand's parts-giant site (common for LatAm/Asia-market vehicles — e.g. a Mitsubishi L200 sold in Ecuador — whose parts the US-market site doesn't carry), it automatically falls back to a PartSouq lookup for that part. OEM_MSRP stays blank in this case (PartSouq doesn't publish MSRP), but OEM_PRECIO/OEM_URL fill in when found, and the cell gets a note explaining the price came from PartSouq.

---

## eBay Lookup (part of OEM PX)

`agent/ebay_service.py` — eBay Browse API.
Returns genuine price (AD) and aftermarket price (AF), both as landed cost (item price + cheapest shipping to the configured zip) — not item price alone.
Genuine vs. aftermarket is classified per listing: either eBay's structured Brand aspect matches the vehicle brand, or the title contains a genuine/OEM keyword. (Two signals, since sellers often don't fill in the structured Brand field even when the title says "OEM Genuine".)
Credentials: `EBAY_APP_ID` + `EBAY_CERT_ID` in `.env`.

---

## AVK / Auvika Lookup (AVKO + AVKI buttons)

⚠ **Brand-based routing fix:** European-vs-not used to be decided purely by VIN WMI prefix (`is_european_vin`, matched against a hardcoded `EUROPEAN_WMIS` list in `config.py`). That list can't cover every regional-assembly plant — a VW built in Argentina/Brazil, for instance, can carry a WMI like `8L7...` that isn't European-assigned at all, even though the vehicle is clearly a VW. This surfaced as AVKO saying "no European parts on this quote" for a VW quote with 15+ parts. Fixed with `is_european(vin, armadora)` in `config.py`: it now checks the quote's own **armadora** field first (authoritative — Inpart states the manufacturer directly) against a `EUROPEAN_BRAND_NAMES` set (VW, Audi, BMW, Mercedes, Volvo, Jaguar, Land Rover, Porsche, Renault, Citroën, Peugeot, Fiat, Alfa Romeo, Seat, Skoda, Opel, etc.), and only falls back to the VIN WMI check when armadora wasn't captured. Every AVK/PartSouq routing decision (`enrich_excel.py`, `generate_avk_list.py`, `generate_partsouq_list.py`) now goes through this shared helper.

⚠ **Staleness fix:** AVKO and "Lista PartSouq" used to only read a `.txt` file that got written as a side effect of running OEM PX. If you imported a new quote but hadn't re-run OEM PX yet, the button would silently hand you the *previous* quote's part numbers — no error, just wrong data with no connection to what's on screen (this is exactly what happened with a Citroën quote returning a stale Mercedes-Benz part list). Both buttons now call a standalone regenerator (`tools/generate_avk_list.py` / `tools/generate_partsouq_list.py`) that reads straight off the live COTIZACION sheet every time, before touching the clipboard — so they can never be stale, whether or not OEM PX has run yet.

- **AVKO**: generates list of OE numbers (no spaces/dashes, 1 per line) → clipboard → paste into AVK bulk search
- **AVKI**: scrapes AVK results and writes to AH (AVK_GENUINE) and AI (AVK_AFTER)
- European brands are identified via `EUROPEAN_WMIS` in `tools/shared/config.py`
- Includes LatAm Mercedes assembly codes: NW1 (Actros trucks), 9BM, 8AD

### AVK bookmarklet ("AVK: Get Prices") — v2 fix

The "Get Prices" bookmarklet (`avk_bookmarklets.html`, Step 2) was scraping for `<table>`/`<tr>`/`<td>` elements, but avkparts.lt's bulk search results are div-based, not a real table — it was silently finding **zero rows every time**, so AVKI had nothing to import. Confirmed live against a real 13-part bulk search. Rewritten against the actual structure:
- `.bulk_single_item` — one per searched part number, containing `.single_bulk_code` (the searched code)
- `.item` — one per supplier offer within that group
- `.column_provider` — supplier code (e.g. `PSA E`, `FCA T1`, `TYC`, `DEPOT`)
- `.column_price_no_tax` / `.column_price_with_tax` — net / gross price

Verified live: correctly extracted 115 supplier rows across 13 parts. Also fixed a price-parsing bug that misread "€81.85" as 8185 (was stripping the decimal point as if it were a thousands separator).

**Genuine vs. aftermarket classification fix:** `fill_avk_prices()` in `excel_writer.py` used to only treat a supplier as genuine if its name literally contained "OEM"/"ORIGINAL"/"GENUINE" — but AVK's real supplier codes are manufacturer-group codes like `PSA E`/`PSA T` (Peugeot-Citroën-DS) or `FCA I`/`FCA T1` (Fiat-Chrysler-Jeep-Alfa), none of which match that wording, so every AVK result was being misclassified as aftermarket. Now also recognizes known manufacturer-group prefixes (`PSA`, `FCA`, `OPEL/PSA`, `VAG`, `BMW`, `MERCEDES`, `VOLVO`, `JLR`) as genuine; independent third-party brands (TYC, DEPOT, AYFAR, L-SERIES, etc.) are still aftermarket.

---

## Key Files

```
workflow-pro/
├── agent/
│   ├── oem_service.py        # OEM scraper + brand/VIN routing
│   └── ebay_service.py       # eBay Finding API
├── tools/
│   ├── import_inpart_clip.py # INPART button logic
│   ├── enrich_excel.py       # OEM PX button logic
│   ├── import_avk_prices.py  # AVKI button logic
│   └── shared/
│       ├── config.py         # EUROPEAN_WMIS, paths, credentials loader
│       ├── excel_writer.py   # xlwings helpers (read/write cotizacion_bulk.xlsm)
│       └── tariff_lookup.py  # Supabase tariff code lookup
├── mcp_server/server.py      # Local MCP tools for Claude
├── inpart_bookmarklet.html   # v7 bookmarklet
├── cotizacion_bulk.xlsm      # Master quotation workbook
├── avk_parts_list.txt        # Generated AVK parts list
└── .env                      # EBAY_APP_ID, EBAY_CERT_ID, INPART_*, SUPABASE_*
```

## Vercel App

React + Vite SPA deployed on Vercel. Stack: React 18, Radix UI, Tailwind, Supabase, React Query. Used as the OEM pricing tool front-end. SPA routing via `vercel.json` (`/* → /index.html`).
