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
    - Username / password fields
    - Accept Terms and Conditions checkbox
    - Concurrent session conflict dialog ("¿Desea continuar? Sí/No")

    Success = URL contains "/AudaPartsWebApp/" (the actual app, not the login site).
    The login site lives under "/AudaPartsSite/" — staying there means login failed.
    """
    print(f"[inpart] Navigating to login page…")
    await page.goto(INPART_LOGIN, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(1500)

    if debug:
        await _screenshot(page, "01_login_page")

    # ── Fill username ──────────────────────────────────────────────────────
    user_sel = "input[name*='user' i], input[id*='user' i], input[type='text']"
    try:
        user_input = page.locator(user_sel).first
        await user_input.fill(USERNAME, timeout=10_000)
        print(f"[inpart] Username filled")
    except Exception as e:
        print(f"[inpart] WARNING: could not fill username field: {e}")

    # ── Fill password ──────────────────────────────────────────────────────
    try:
        pw_input = page.locator("input[type='password']").first
        await pw_input.click(timeout=5_000)
        await pw_input.fill(PASSWORD, timeout=5_000)
        print(f"[inpart] Password filled")
    except Exception as e:
        print(f"[inpart] WARNING: could not fill password field: {e}")

    # ── Check Terms and Conditions ─────────────────────────────────────────
    try:
        checkbox = page.locator("input[type='checkbox']").first
        if not await checkbox.is_checked():
            await checkbox.click(timeout=5_000)
            print("[inpart] Terms checkbox checked")
        else:
            print("[inpart] Terms checkbox already checked")
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
        print("[inpart] Sign In clicked")
    except Exception as e:
        print(f"[inpart] WARNING: could not click Sign In: {e}")

    await page.wait_for_timeout(3000)

    if debug:
        await _screenshot(page, "03_after_signin")

    # ── Handle concurrent session conflict dialog ───────────────────────────
    # Dialog: "usted ya ha iniciado sesión en otro terminal. ¿Desea continuar?"
    # Buttons: "Sí"/"Si" — use JavaScript to find any matching button/link/input
    # (Playwright :has-text is case-sensitive and accent-sensitive; JS is safer)
    for attempt in range(3):
        try:
            clicked = await page.evaluate("""
                () => {
                    const all = [
                        ...document.querySelectorAll(
                            'button, a, input[type="button"], input[type="submit"]'
                        )
                    ];
                    const btn = all.find(el => {
                        const t = (el.textContent || el.value || '').trim();
                        return t === 'Si' || t === 'Sí' || t === 'SI'
                            || t === 'Yes' || t === 'YES';
                    });
                    if (btn) {
                        btn.click();
                        return (btn.tagName + ': ' + (btn.textContent || btn.value || '').trim());
                    }
                    return null;
                }
            """)
            if clicked:
                print(f"[inpart] Session dialog Sí clicked via JS: {clicked}")
                await page.wait_for_timeout(6000)   # allow full page reload
                break
            elif attempt < 2:
                print(f"[inpart] No Sí button yet (attempt {attempt+1}) — waiting 2s…")
                await page.wait_for_timeout(2000)
        except Exception as ex:
            print(f"[inpart] Session dialog attempt {attempt+1} error: {ex}")
            await page.wait_for_timeout(2000)

    if debug:
        await _screenshot(page, "04_login_result")

    # ── Verify login ───────────────────────────────────────────────────────
    # SUCCESS = URL is under /AudaPartsWebApp/ (the supplier portal app)
    # FAILURE = still under /AudaPartsSite/ (the marketing/login site)
    current_url = page.url
    logged_in = "/AudaPartsWebApp/" in current_url

    if not logged_in:
        print(f"[inpart] Not on AudaPartsWebApp after login ({current_url}) — retrying nav…")
        try:
            await page.goto(INPART_SEARCH, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2000)
            current_url = page.url
            logged_in = "/AudaPartsWebApp/" in current_url
        except Exception as e:
            print(f"[inpart] Direct nav to search failed: {e}")

    print(f"[inpart] Login {'SUCCEEDED' if logged_in else 'FAILED'} — URL: {page.url}")
    return logged_in


# ── Search page ───────────────────────────────────────────────────────────────

async def get_pending_quotations(page, days_back=7, debug=False) -> list[dict]:
    """
    Navigate to the search page and fetch all pending quotations.

    Returns list of dicts with keys:
      aseguradora, cotizacion_id, taller, poliza, siniestro,
      matricula, armadora, fecha, pendientes

    Fixes vs original:
    - Dates set via JavaScript (handles readonly ASP.NET calendar pickers)
    - Results table found by <th> content ("Cotización"), not by row count
      (the page layout tables have more rows than the 1-2 row results GridView)
    - Table fully parsed in JS for speed and reliability
    """
    print(f"[inpart] Fetching pending quotations (last {days_back} days)…")
    await page.goto(INPART_SEARCH, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(2000)

    if debug:
        await _screenshot(page, "05_search_page")
        await _dump_html(page, "05_search_page")

    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%d/%m/%Y")
    date_to   = datetime.now().strftime("%d/%m/%Y")
    print(f"[inpart] Date range: {date_from} → {date_to}")

    # ── Fill dates via JavaScript ──────────────────────────────────────────
    # ASP.NET calendar picker inputs are often readonly; .fill() is silently
    # ignored on them.  We remove readonly, set the value, and fire all events.
    date_fill_result = await page.evaluate(f"""
        () => {{
            const allInputs = [...document.querySelectorAll('input[type="text"]')];

            // Priority 1: inputs whose id/name contains 'fecha' (case-insensitive)
            let dateInputs = allInputs.filter(el =>
                el.id.toLowerCase().includes('fecha') ||
                el.name.toLowerCase().includes('fecha')
            );

            // Priority 2: inputs that already hold a dd/mm/yyyy value
            if (dateInputs.length < 2) {{
                dateInputs = allInputs.filter(el =>
                    /\d{{2}}\/\d{{2}}\/\d{{4}}/.test(el.value)
                );
            }}

            // Priority 3: first two text inputs on the form
            if (dateInputs.length < 2) {{
                dateInputs = allInputs.slice(0, 2);
            }}

            function setVal(el, val) {{
                if (!el) return false;
                const wasReadonly = el.readOnly;
                el.readOnly = false;
                el.value = val;
                ['input', 'change', 'blur'].forEach(evt =>
                    el.dispatchEvent(new Event(evt, {{bubbles: true}}))
                );
                if (wasReadonly) el.readOnly = true;
                return true;
            }}

            const r = {{
                found: dateInputs.length,
                ids: dateInputs.slice(0, 2).map(e => e.id || e.name || '?'),
                from: false,
                to:   false,
            }};
            if (dateInputs.length >= 1) r.from = setVal(dateInputs[0], '{date_from}');
            if (dateInputs.length >= 2) r.to   = setVal(dateInputs[1], '{date_to}');
            return r;
        }}
    """)
    print(f"[inpart] Date fill: {date_fill_result}")
    await page.wait_for_timeout(500)

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
                    print(f"[inpart] Status filter → {opt['t']}")
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
        print("[inpart] WARNING: Date range too wide — retrying with 7 days…")
        return await get_pending_quotations(page, days_back=7, debug=debug)

    # ── Parse results table via JavaScript ────────────────────────────────
    # BUG in original: picking the table with the most rows chose a layout
    # table (many rows) instead of the 2-row GridView results table.
    # FIX: find the table that has a <th> containing "cotizaci".
    result = await page.evaluate("""
        () => {
            // Find the GridView results table by its <th> content
            let resultsTable = null;
            for (const tbl of document.querySelectorAll('table')) {
                const ths = [...tbl.querySelectorAll('th')];
                if (ths.some(th => th.innerText.toLowerCase().includes('cotizaci'))) {
                    resultsTable = tbl;
                    break;
                }
            }

            if (!resultsTable) {
                return {error: 'no_results_table', quotations: [], headers: []};
            }

            // Header row
            const headerRow = resultsTable.querySelector('tr');
            if (!headerRow) return {error: 'no_header_row', quotations: [], headers: []};

            const headerCells = [...headerRow.querySelectorAll('th, td')];
            const headers = headerCells.map(c => c.innerText.trim().toLowerCase());

            const fi = (keywords) => headers.findIndex(h =>
                keywords.some(kw => h.includes(kw))
            );

            const idx = {
                cot:        fi(['cotizaci']),
                aseg:       fi(['origen', 'aseg', 'compañ']),
                taller:     fi(['taller']),
                poliza:     fi(['póliza', 'poliza', 'documento']),
                siniestro:  fi(['siniestro']),
                matricula:  fi(['matr', 'placa']),
                armadora:   fi(['armadora', 'marca']),
                fecha:      fi(['fecha']),
                pendientes: fi(['pendiente']),
            };

            const quotations = [];
            const rows = [...resultsTable.querySelectorAll('tr')].slice(1);

            for (const row of rows) {
                const cells = [...row.querySelectorAll('td')];
                if (cells.length < 3) continue;

                const g = (i) => (i >= 0 && i < cells.length)
                    ? cells[i].innerText.trim() : '';

                const cotId = g(idx.cot);
                if (!cotId || !/\d{3,}/.test(cotId)) continue;

                const m = cotId.match(/\d+/);
                if (!m) continue;

                quotations.push({
                    cotizacion_id: m[0],
                    aseguradora:   g(idx.aseg),
                    taller:        g(idx.taller),
                    poliza:        g(idx.poliza),
                    siniestro:     g(idx.siniestro),
                    matricula:     g(idx.matricula),
                    armadora:      g(idx.armadora),
                    fecha:         g(idx.fecha),
                    pendientes:    g(idx.pendientes),
                });
            }

            return {error: null, headers, idx, quotations};
        }
    """)

    if result.get("error"):
        print(f"[inpart] Table parse error: {result['error']}")
        # Log body snippet for debugging
        snippet = body[:500].replace('\n', ' ')
        print(f"[inpart] Page body snippet: {snippet}")
        return []

    print(f"[inpart] Table headers found: {result.get('headers')}")
    print(f"[inpart] Column indexes: {result.get('idx')}")

    quotations = []
    for q in result.get("quotations", []):
        q["vin"]   = None
        q["partes"] = []
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


# ── Diagnostic helper ─────────────────────────────────────────────────────────

async def diagnose_connection(headless: bool = True) -> dict:
    """
    Run a login + search and return a full diagnostic report as a dict.
    Called by GET /inpart/diagnose — no screenshots, all JSON.
    """
    from datetime import datetime, timedelta

    info: dict = {
        "login":          {"success": False, "url_after": "", "error": ""},
        "search_page":    {"url": "", "title": "", "inputs": [], "tables_before": []},
        "search_results": {"url": "", "body_snippet": "", "result_text": "",
                           "tables_after": [], "buscar_error": ""},
        "fatal": "",
    }

    if not USERNAME or not PASSWORD:
        info["fatal"] = "INPART_USERNAME or INPART_PASSWORD not set"
        return info

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-dev-shm-usage"],
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
        )
        page = await ctx.new_page()
        page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))

        try:
            # ── Inspect login form BEFORE attempting login ─────────────────
            await page.goto(INPART_LOGIN, wait_until="domcontentloaded", timeout=60_000)
            await page.wait_for_timeout(1500)
            info["login_form"] = await page.evaluate("""
                () => ({
                    url: window.location.href,
                    textInputs: [...document.querySelectorAll('input[type="text"]')].map(el => ({
                        id: el.id, name: el.name, value: el.value,
                        visible: el.offsetWidth > 0 && el.offsetHeight > 0
                    })),
                    passwordInputs: [...document.querySelectorAll('input[type="password"]')].map(el => ({
                        id: el.id, name: el.name, visible: el.offsetWidth > 0
                    })),
                    checkboxes: [...document.querySelectorAll('input[type="checkbox"]')].map(el => ({
                        id: el.id, name: el.name, checked: el.checked,
                        visible: el.offsetWidth > 0
                    })),
                    buttons: [...document.querySelectorAll(
                        'input[type="submit"], button, input[type="button"]'
                    )].map(el => ({
                        id: el.id, value: el.value,
                        text: el.textContent?.trim().substring(0, 40),
                        type: el.type, visible: el.offsetWidth > 0
                    })),
                })
            """)

            # ── Login ──────────────────────────────────────────────────────
            try:
                ok = await login(page, debug=False)
                info["login"]["success"] = ok
                info["login"]["url_after"] = page.url
            except Exception as e:
                info["login"]["error"] = str(e)
                info["login"]["url_after"] = page.url

            # ── Search page ────────────────────────────────────────────────
            await page.goto(INPART_SEARCH, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(2000)
            info["search_page"]["url"]   = page.url
            info["search_page"]["title"] = await page.title()

            # What text inputs exist?
            inputs_info = await page.evaluate("""
                () => [...document.querySelectorAll('input[type="text"]')].map(el => ({
                    id:       el.id,
                    name:     el.name,
                    value:    el.value,
                    readonly: el.readOnly,
                    disabled: el.disabled,
                }))
            """)
            info["search_page"]["inputs"] = inputs_info

            # What tables exist before search?
            tables_before = await page.evaluate("""
                () => [...document.querySelectorAll('table')].map((tbl, i) => ({
                    index:   i,
                    rows:    tbl.querySelectorAll('tr').length,
                    headers: [...tbl.querySelectorAll('th')].map(th => th.innerText.trim()),
                })).filter(t => t.rows > 0)
            """)
            info["search_page"]["tables_before"] = tables_before

            # ── Try date fill + search ─────────────────────────────────────
            date_from = (datetime.now() - timedelta(days=7)).strftime("%d/%m/%Y")
            date_to   = datetime.now().strftime("%d/%m/%Y")

            fill_result = await page.evaluate(f"""
                () => {{
                    const all = [...document.querySelectorAll('input[type="text"]')];
                    const fecha = all.filter(el =>
                        el.id.toLowerCase().includes('fecha') ||
                        el.name.toLowerCase().includes('fecha') ||
                        /\\d{{2}}\\/\\d{{2}}\\/\\d{{4}}/.test(el.value)
                    );
                    function set(el, v) {{
                        el.readOnly = false;
                        el.value = v;
                        ['input','change','blur'].forEach(n =>
                            el.dispatchEvent(new Event(n, {{bubbles:true}}))
                        );
                    }}
                    if (fecha.length >= 1) set(fecha[0], '{date_from}');
                    if (fecha.length >= 2) set(fecha[1], '{date_to}');
                    return {{ found: fecha.length, ids: fecha.slice(0,2).map(e=>e.id||e.name||'?') }};
                }}
            """)
            info["search_results"]["date_fill"] = fill_result

            # Set status to Pendiente
            try:
                selects = page.locator("select")
                n = await selects.count()
                for i in range(n):
                    opts = await selects.nth(i).evaluate(
                        "el => Array.from(el.options).map(o=>({v:o.value,t:o.text}))"
                    )
                    for opt in opts:
                        if "pendiente" in opt.get("t","").lower():
                            await selects.nth(i).select_option(value=opt["v"])
                            break
            except Exception:
                pass

            # Click Buscar
            try:
                await page.locator("input[value='Buscar' i]").first.click(timeout=5_000)
                await page.wait_for_timeout(4000)
            except Exception as e:
                info["search_results"]["buscar_error"] = str(e)

            info["search_results"]["url"] = page.url
            body = await page.inner_text("body")
            info["search_results"]["body_snippet"] = body[:1500]

            # Look for "Resultado de la Búsqueda" text
            import re as _re
            m = _re.search(r'resultado[^:\n]*:\s*\d+', body, _re.IGNORECASE)
            if m:
                info["search_results"]["result_text"] = m.group(0)

            # Tables after search
            tables_after = await page.evaluate("""
                () => [...document.querySelectorAll('table')].map((tbl, i) => {
                    const rows = [...tbl.querySelectorAll('tr')];
                    return {
                        index:      i,
                        rows:       rows.length,
                        headers:    [...tbl.querySelectorAll('th')].map(th=>th.innerText.trim()),
                        first_data: rows.slice(0,3).map(r=>
                            [...r.querySelectorAll('td')].map(td=>td.innerText.trim().substring(0,40))
                        ),
                    };
                }).filter(t => t.rows > 0)
            """)
            info["search_results"]["tables_after"] = tables_after

        except Exception as e:
            info["fatal"] = str(e)
        finally:
            await browser.close()

    return info
