"""
inpart_scraper.py — Audatex Inpart scraper
==========================================
Scrapes all pending quotation requests from the Inpart supplier portal.

Credentials are read from environment variables only:
  INPART_USERNAME  — e.g. MX304177
  INPART_PASSWORD  — never hardcoded here

Usage as a module:
  from inpart_scraper import scrape_pending_quotations
  quotations = await scrape_pending_quotations()   # list of dicts

Usage standalone (for debugging):
  python inpart_scraper.py --debug
"""

import asyncio
import os
import re
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ── Constants ─────────────────────────────────────────────────────────────────
INPART_BASE   = "https://inpart-la.audatex.com.mx"
INPART_LOGIN  = f"{INPART_BASE}/AudaPartsSite/"
INPART_SEARCH = f"{INPART_BASE}/AudaPartsWebApp/frmQuotationSupplierSearch.aspx"

USERNAME = os.environ.get("INPART_USERNAME", "")
PASSWORD = os.environ.get("INPART_PASSWORD", "")

VIN_RE = re.compile(r'\b[A-HJ-NPR-Z0-9]{17}\b')

DEBUG_DIR = Path(__file__).parent / "debug_screenshots"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _screenshot(page, name: str):
    """Save a debug screenshot if debug mode is on."""
    DEBUG_DIR.mkdir(exist_ok=True)
    path = DEBUG_DIR / f"{name}_{datetime.now().strftime('%H%M%S')}.png"
    await page.screenshot(path=str(path), full_page=True)
    print(f"  [debug] screenshot → {path.name}")


async def _dump_html(page, name: str):
    """Save a debug HTML dump."""
    DEBUG_DIR.mkdir(exist_ok=True)
    path = DEBUG_DIR / f"{name}_{datetime.now().strftime('%H%M%S')}.html"
    path.write_text(await page.content(), encoding="utf-8")
    print(f"  [debug] html dump  → {path.name}")


# ── Login ─────────────────────────────────────────────────────────────────────

async def login(page, debug=False) -> bool:
    """
    Log into Inpart.
    Handles:
    - Username / password fields (correct order: fill pw, THEN check terms)
    - Accept Terms and Conditions checkbox
    - Concurrent session conflict dialog ("¿Sí/No?")

    Returns True if login succeeded.
    """
    print(f"[inpart] Navigating to login page…")
    await page.goto(INPART_LOGIN, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(1500)

    if debug:
        await _screenshot(page, "01_login_page")

    # ── Fill username ──────────────────────────────────────────────────────
    # The username field typically has name/id containing "user" or "User"
    user_sel = "input[name*='user' i], input[id*='user' i], input[type='text']"
    try:
        user_input = page.locator(user_sel).first
        await user_input.fill(USERNAME, timeout=10_000)
    except Exception as e:
        print(f"[inpart] WARNING: could not fill username field: {e}")

    # ── Fill password FIRST (before checking terms to avoid clearing) ──────
    try:
        pw_input = page.locator("input[type='password']").first
        await pw_input.click(timeout=5_000)
        await pw_input.fill(PASSWORD, timeout=5_000)
    except Exception as e:
        print(f"[inpart] WARNING: could not fill password field: {e}")

    # ── Check Terms and Conditions ─────────────────────────────────────────
    try:
        checkbox = page.locator("input[type='checkbox']").first
        if not await checkbox.is_checked():
            await checkbox.click(timeout=5_000)
    except Exception as e:
        print(f"[inpart] WARNING: could not check terms checkbox: {e}")

    if debug:
        await _screenshot(page, "02_before_signin")

    # ── Click Sign In ──────────────────────────────────────────────────────
    try:
        sign_in = page.locator(
            "input[type='submit'], input[value*='Sign' i], button:has-text('Sign In')"
        ).first
        await sign_in.click(timeout=5_000)
    except Exception as e:
        print(f"[inpart] WARNING: could not click Sign In: {e}")

    await page.wait_for_timeout(3000)

    if debug:
        await _screenshot(page, "03_after_signin")

    # ── Handle concurrent session dialog ───────────────────────────────────
    # Message: "usted ya ha iniciado sesión en otro terminal. Si continúa..."
    try:
        yes_btn = page.locator(
            "a:has-text('Sí'), button:has-text('Sí'), input[value='Sí'],"
            "a:has-text('Si'), button:has-text('Si'), input[value='Si']"
        )
        count = await yes_btn.count()
        if count > 0:
            print("[inpart] Session conflict dialog detected — clicking Sí…")
            await yes_btn.first.click(timeout=5_000)
            await page.wait_for_timeout(3000)
    except Exception:
        pass

    # ── Verify login ───────────────────────────────────────────────────────
    current_url = page.url.lower()
    logged_in = (
        "login" not in current_url
        and "audasite" not in current_url.split("?")[0].lower()
        and ("audaparts" in current_url or "panel" in current_url or "search" in current_url)
    )

    if not logged_in:
        # Sometimes we're redirected to the search page directly
        # Try navigating there explicitly
        await page.goto(INPART_SEARCH, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2000)
        current_url = page.url.lower()
        logged_in = "search" in current_url or "quotation" in current_url

    if debug:
        await _screenshot(page, "04_login_result")

    print(f"[inpart] Login {'succeeded' if logged_in else 'FAILED'} — URL: {page.url}")
    return logged_in


# ── Search page ───────────────────────────────────────────────────────────────

async def get_pending_quotations(page, days_back=7, debug=False) -> list[dict]:
    """
    Navigate to the search page and fetch all pending quotations.

    Returns list of dicts with keys:
      aseguradora, cotizacion_id, taller, poliza, siniestro,
      matricula, armadora, fecha, pendientes
    """
    print(f"[inpart] Fetching pending quotations (last {days_back} days)…")
    await page.goto(INPART_SEARCH, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(2000)

    if debug:
        await _screenshot(page, "05_search_page")
        await _dump_html(page, "05_search_page")

    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%d/%m/%Y")
    date_to   = datetime.now().strftime("%d/%m/%Y")

    # ── Fill date range ────────────────────────────────────────────────────
    # "Fecha Desde" is the first date text input on the form
    try:
        date_inputs = page.locator("input[type='text'][id*='Fecha' i], input[type='text'][name*='Fecha' i]")
        count = await date_inputs.count()
        if count >= 1:
            await date_inputs.nth(0).triple_click()
            await date_inputs.nth(0).fill(date_from)
        if count >= 2:
            await date_inputs.nth(1).triple_click()
            await date_inputs.nth(1).fill(date_to)
        else:
            # Fall back: fill first two text inputs on the page
            all_text = page.locator("input[type='text']")
            n = await all_text.count()
            if n >= 1:
                await all_text.nth(0).triple_click()
                await all_text.nth(0).fill(date_from)
            if n >= 2:
                await all_text.nth(1).triple_click()
                await all_text.nth(1).fill(date_to)
    except Exception as e:
        print(f"[inpart] WARNING: could not fill dates: {e}")

    # ── Set Status = Pendiente ─────────────────────────────────────────────
    try:
        selects = page.locator("select")
        n = await selects.count()
        for i in range(n):
            options = await selects.nth(i).evaluate(
                "el => Array.from(el.options).map(o => ({v: o.value, t: o.text}))"
            )
            for opt in options:
                if "pendiente" in opt.get("t", "").lower():
                    await selects.nth(i).select_option(value=opt["v"])
                    print(f"[inpart] Set status filter to: {opt['t']}")
                    break
    except Exception as e:
        print(f"[inpart] WARNING: could not set status filter: {e}")

    # ── Click Buscar ───────────────────────────────────────────────────────
    try:
        buscar = page.locator(
            "input[value='Buscar' i], input[value*='Buscar' i],"
            "button:has-text('Buscar'), a:has-text('Buscar')"
        ).first
        await buscar.click(timeout=5_000)
    except Exception as e:
        print(f"[inpart] WARNING: could not click Buscar: {e}")

    await page.wait_for_timeout(4000)

    if debug:
        await _screenshot(page, "06_search_results")
        await _dump_html(page, "06_search_results")

    # ── Check for "period exceeded" error ─────────────────────────────────
    body = await page.inner_text("body")
    if "período excedido" in body.lower() or "periodo excedido" in body.lower():
        print("[inpart] WARNING: Date range too wide — retrying with 7 days max…")
        return await get_pending_quotations(page, days_back=7, debug=debug)

    # ── Parse results table ────────────────────────────────────────────────
    # The results are in a GridView / HTML table. We find all tables and pick
    # the one with the most rows that looks like quotation data.
    quotations = []

    tables = page.locator("table")
    ntables = await tables.count()

    best_table = None
    best_rows  = 0

    for ti in range(ntables):
        rows = tables.nth(ti).locator("tr")
        n = await rows.count()
        if n > best_rows:
            best_rows  = n
            best_table = tables.nth(ti)

    if best_table is None or best_rows < 2:
        print("[inpart] No results table found.")
        return []

    # Detect header row to understand column order
    header_row = best_table.locator("tr").nth(0)
    headers = []
    header_cells = header_row.locator("th, td")
    nh = await header_cells.count()
    for i in range(nh):
        txt = (await header_cells.nth(i).inner_text()).strip().lower()
        headers.append(txt)

    print(f"[inpart] Table headers: {headers}")

    # Map header text → column index (flexible matching)
    def col(keywords):
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in h:
                    return i
        return None

    idx_cot        = col(["cotizaci"])         # "Cotización"
    idx_aseg       = col(["origen", "aseg", "compañ"])
    idx_taller     = col(["taller"])
    idx_poliza     = col(["póliza", "poliza", "documento"])
    idx_siniestro  = col(["siniestro"])
    idx_matricula  = col(["matrícula", "matricula", "placa"])
    idx_armadora   = col(["armadora", "marca"])
    idx_fecha      = col(["fecha"])
    idx_pendientes = col(["pendiente"])

    print(f"[inpart] Column map: cot={idx_cot}, aseg={idx_aseg}, taller={idx_taller}, "
          f"matricula={idx_matricula}, pendientes={idx_pendientes}")

    rows = best_table.locator("tr")
    nrows = await rows.count()

    for ri in range(1, nrows):
        row = rows.nth(ri)
        cells = row.locator("td")
        nc = await cells.count()
        if nc < 3:
            continue

        async def cell_text(idx):
            if idx is None or idx >= nc:
                return ""
            return (await cells.nth(idx).inner_text()).strip()

        cot_id = await cell_text(idx_cot)

        # Skip rows without a numeric quotation ID
        if not cot_id or not re.search(r'\d{3,}', cot_id):
            continue

        q = {
            "cotizacion_id": re.search(r'\d+', cot_id).group(0),
            "aseguradora":   await cell_text(idx_aseg),
            "taller":        await cell_text(idx_taller),
            "poliza":        await cell_text(idx_poliza),
            "siniestro":     await cell_text(idx_siniestro),
            "matricula":     await cell_text(idx_matricula),
            "armadora":      await cell_text(idx_armadora),
            "fecha":         await cell_text(idx_fecha),
            "pendientes":    await cell_text(idx_pendientes),
            # detail will be filled by get_quotation_detail()
            "vin":           None,
            "partes":        [],
        }
        quotations.append(q)
        print(f"[inpart]   → COT {q['cotizacion_id']} | {q['aseguradora']} | "
              f"{q['matricula']} | {q['pendientes']} piezas pendientes")

    print(f"[inpart] Found {len(quotations)} pending quotation(s).")
    return quotations


# ── Detail page ───────────────────────────────────────────────────────────────

# Exact IDs discovered from live page inspection
_DETAIL_TABLE_ID = (
    "ctl00_cphBody_tbcAnswerQuotation_tabItems"
    "_ucQuotationSupplierAnswerItems_dtlAnswerPendingItem"
)
_TAB_ITEMS_ID = "__tab_ctl00_cphBody_tbcAnswerQuotation_tabItems"
_TAB_DATOS_ID = "__tab_ctl00_cphBody_tbcAnswerQuotation_tabQuotationData"
_PANEL_DATOS_ID = "ctl00_cphBody_tbcAnswerQuotation_tabQuotationData"


async def get_quotation_detail(page, cotizacion_id: str, debug=False) -> dict:
    """
    Open the detail page for a specific quotation and scrape:
      Tab "Items Cotización" — parts list: [{parte, descripcion}]
      Tab "Datos Cotización" — case info: vin/chasis, matricula, siniestro,
                               aseguradora, taller, año, armadora

    Detail page URL pattern (confirmed):
      frmQuotationSupplierAnswer.aspx?IdQuotation=<base64-encoded-id>

    Strategy: we capture the IdQuotation from the Visualizar button's onclick,
    then navigate directly to the detail page.
    """
    print(f"[inpart] Fetching detail for COT {cotizacion_id}…")

    # Navigate to search and filter by this specific cotizacion
    await page.goto(INPART_SEARCH, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(2000)

    # Fill cotizacion number filter (first text input on the form)
    try:
        cot_input = page.locator(
            "input[id*='Cot'][type='text'], input[name*='Cot'][type='text']"
        ).first
        if await cot_input.count() == 0:
            cot_input = page.locator("input[type='text']").first
        await cot_input.fill(str(cotizacion_id))
    except Exception as e:
        print(f"[inpart] WARNING: could not fill cotizacion filter: {e}")

    # Click Buscar
    try:
        await page.locator("input[value='Buscar' i], button:has-text('Buscar')").first.click(timeout=5_000)
    except Exception as e:
        print(f"[inpart] WARNING: Buscar click failed: {e}")

    await page.wait_for_timeout(3000)

    # ── Capture the detail URL from the Visualizar onclick before clicking ─
    # The button calls window.open(url, ...) — we extract the URL from JS
    detail_url = None
    try:
        detail_url = await page.evaluate("""
            () => {
                // Find the first image-type input (Visualizar button)
                const btn = document.querySelector('input[type="image"]');
                if (!btn) return null;
                // The onclick typically has something like:
                //   window.open('frmQuotationSupplierAnswer.aspx?IdQuotation=XXX', ...)
                const onclick = btn.getAttribute('onclick') || '';
                const m = onclick.match(/window\\.open\\('([^']+)'/);
                return m ? m[1] : null;
            }
        """)
    except Exception:
        pass

    if detail_url:
        # Navigate directly to the detail page (no popup needed)
        full_url = f"{INPART_BASE}/AudaPartsWebApp/{detail_url.lstrip('/')}"
        print(f"[inpart] Navigating directly to: {full_url}")
        await page.goto(full_url, wait_until="domcontentloaded", timeout=45_000)
    else:
        # Fallback: override window.open and click the button
        print(f"[inpart] Could not extract detail URL — using window.open override")
        await page.add_init_script("""
            window.open = function(url, target, specs) {
                if (url && url !== 'about:blank') {
                    window.location.href = url;
                }
                return window;
            };
        """)
        try:
            visualizar = page.locator("input[type='image']").first
            if await visualizar.count() > 0:
                await visualizar.click(timeout=5_000)
            else:
                v2 = page.locator("a[title*='isualiz' i], input[title*='isualiz' i]").first
                await v2.click(timeout=5_000)
        except Exception as e:
            print(f"[inpart] WARNING: Visualizar click failed: {e}")

    await page.wait_for_timeout(3000)

    if debug:
        await _screenshot(page, f"08_cot{cotizacion_id}_detail")

    actual_url = page.url
    print(f"[inpart] On detail page: {actual_url}")

    result = {
        "cotizacion_id": cotizacion_id,
        "detail_url":    actual_url,
        "vin":           None,
        "matricula":     None,
        "siniestro":     None,
        "aseguradora":   None,
        "taller":        None,
        "armadora":      None,
        "ano_modelo":    None,
        "partes":        [],
    }

    # ── Tab 1 "Items Cotización": Parts list ───────────────────────────────
    # Make sure we're on the items tab
    try:
        items_tab = page.locator(f"#{_TAB_ITEMS_ID}")
        if await items_tab.count() > 0:
            await items_tab.click(timeout=3_000)
            await page.wait_for_timeout(800)
    except Exception:
        pass

    result["partes"] = await _scrape_parts_table(page)
    print(f"[inpart]   Parts found: {len(result['partes'])}")

    # ── Tab 2 "Datos Cotización": Case info ────────────────────────────────
    try:
        datos_tab = page.locator(f"#{_TAB_DATOS_ID}")
        if await datos_tab.count() > 0:
            await datos_tab.click(timeout=5_000)
            await page.wait_for_timeout(1500)

            if debug:
                await _screenshot(page, f"09_cot{cotizacion_id}_datos")

            result.update(await _scrape_case_info(page))
        else:
            print(f"[inpart] WARNING: Datos Cotización tab not found")
    except Exception as e:
        print(f"[inpart] WARNING: could not read Datos tab: {e}")
        # Fallback VIN search
        try:
            body = await page.inner_text("body")
            vin_match = VIN_RE.search(body)
            if vin_match:
                result["vin"] = vin_match.group(0)
        except Exception:
            pass

    return result


async def _scrape_parts_table(page) -> list[dict]:
    """
    Extract parts from the Items Cotización tab.

    The table has this structure (confirmed from live inspection):
      6-cell rows: [Pieza Equiv | Grupo | PartNumber | SerialNum | Descripción | Checkbox]
      Interleaved with multi-cell price-form rows (28+ cells) — those are skipped.

    Internal Audatex codes look like: 15-digit numeric strings starting with '2607...'
    Real OEM part numbers: alphanumeric with spaces (e.g. '52119 0K820')
    """
    parts = []

    # Use the confirmed table ID
    js_result = await page.evaluate(f"""
        () => {{
            const table = document.getElementById('{_DETAIL_TABLE_ID}');
            if (!table) return [];
            const parts = [];
            for (const row of table.querySelectorAll('tr')) {{
                const cells = [...row.querySelectorAll('td')];
                if (cells.length !== 6) continue;           // part rows have exactly 6 cells
                const partNum = cells[2].innerText.trim();
                const desc    = cells[4].innerText.trim();
                // Skip header row and empty rows
                if (!partNum || partNum === 'PartNumber' || partNum === 'Pieza Equivalente') continue;
                parts.push({{ parte: partNum, descripcion: desc }});
            }}
            return parts;
        }}
    """)

    return js_result or []


async def _scrape_case_info(page) -> dict:
    """
    Extract case info from the Datos Cotización tab panel.

    The panel ID is confirmed: ctl00_cphBody_tbcAnswerQuotation_tabQuotationData
    Structure: label-value pairs in <tr> rows — each row has alternating label/value cells.
    """
    info = {
        "vin":         None,
        "matricula":   None,
        "siniestro":   None,
        "aseguradora": None,
        "taller":      None,
        "armadora":    None,
        "ano_modelo":  None,
        "valuador":    None,
        "poliza":      None,
    }

    js_result = await page.evaluate(f"""
        () => {{
            const panel = document.getElementById('{_PANEL_DATOS_ID}');
            if (!panel) return null;

            const result = {{}};
            const rows = panel.querySelectorAll('tr');
            for (const row of rows) {{
                const cells = [...row.querySelectorAll('td')];
                // Read label: value pairs across the row
                for (let i = 0; i < cells.length - 1; i++) {{
                    const label = cells[i].innerText.trim().toLowerCase();
                    const value = cells[i + 1].innerText.trim();
                    if (!label || !value) continue;
                    if (label.includes('chasis')) result.vin = value;
                    else if (label.includes('matr')) result.matricula = value;
                    else if (label.includes('siniestro')) result.siniestro = value;
                    else if (label.includes('aseguradora')) result.aseguradora = value;
                    else if (label.includes('taller')) result.taller = value;
                    else if (label.includes('armadora')) result.armadora = value;
                    else if (label.includes('año modelo') || label.includes('ano modelo')) result.ano_modelo = value;
                    else if (label.includes('valuador')) result.valuador = value;
                    else if (label.includes('póliza') || label.includes('poliza')) result.poliza = value;
                }}
            }}
            return result;
        }}
    """)

    if js_result:
        info.update({k: v for k, v in js_result.items() if v})

    # Fallback: VIN regex from body text
    if not info["vin"]:
        try:
            body = await page.inner_text("body")
            m = VIN_RE.search(body)
            if m:
                info["vin"] = m.group(0)
        except Exception:
            pass

    return info


# ── Main scraping function ────────────────────────────────────────────────────

async def scrape_pending_quotations(
    days_back: int = 7,
    fetch_details: bool = True,
    debug: bool = False,
    headless: bool = True,
) -> list[dict]:
    """
    Full pipeline:
      1. Login to Inpart
      2. Get list of pending quotations
      3. For each, fetch detail page (parts + case info)

    Returns list of quotation dicts.
    """
    if not USERNAME or not PASSWORD:
        raise ValueError(
            "INPART_USERNAME and INPART_PASSWORD environment variables must be set."
        )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="es-MX",
            timezone_id="America/Mexico_City",
            # Accept popups but we override window.open anyway
            java_script_enabled=True,
        )
        page = await ctx.new_page()
        # Ignore certificate / mixed-content warnings
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))

        try:
            ok = await login(page, debug=debug)
            if not ok:
                print("[inpart] Login failed — aborting.")
                return []

            quotations = await get_pending_quotations(page, days_back=days_back, debug=debug)

            if fetch_details:
                for q in quotations:
                    try:
                        detail = await get_quotation_detail(
                            page, q["cotizacion_id"], debug=debug
                        )
                        q.update(detail)
                    except Exception as e:
                        print(f"[inpart] ERROR getting detail for COT {q['cotizacion_id']}: {e}")

        finally:
            await browser.close()

    return quotations


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Inpart pending quotation scraper")
    ap.add_argument("--debug",      action="store_true", help="Save debug screenshots + HTML")
    ap.add_argument("--no-details", action="store_true", help="Skip detail page scraping")
    ap.add_argument("--days",       type=int, default=7, help="Days back for search (default 7)")
    ap.add_argument("--visible",    action="store_true", help="Run with visible browser")
    args = ap.parse_args()

    quotations = asyncio.run(scrape_pending_quotations(
        days_back=args.days,
        fetch_details=not args.no_details,
        debug=args.debug,
        headless=not args.visible,
    ))

    print("\n" + "="*60)
    print(f"RESULTS: {len(quotations)} quotation(s)")
    print("="*60)
    for q in quotations:
        print(json.dumps(q, indent=2, ensure_ascii=False))
