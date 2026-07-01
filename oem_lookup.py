#!/usr/bin/env python3
"""
OEM Price Lookup Tool — cotizacion_bulk.xlsm
============================================
Reads auction blocks from the Excel file, fetches OEM prices via Playwright,
and writes results to  oem_results_temp.csv  (same folder as the script).

The VBA macro in OEMLookup.bas reads that CSV and fills the cells — so Excel
never needs to be closed or reopened.

Usage (called automatically by the Excel button):
  python oem_lookup.py [--auction N] [--all] [--headless]
"""

import asyncio, re, sys, csv, argparse, openpyxl
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

try:
    from playwright_stealth import stealth_async
    STEALTH = True
except ImportError:
    STEALTH = False
    print('NOTE: playwright-stealth not installed (run: pip install playwright-stealth)')
    print('      Continuing without stealth — site may block automation.')

# ── Column indices in COTIZACION (1-based) ────────────────────────────────────
COL_PARTE      = 1   # A
COL_DESC       = 2   # B
COL_OEM_MSRP   = 26  # Z
COL_OEM_PRECIO = 27  # AA
COL_VIN_FITS   = 28  # AB
COL_OEM_URL    = 29  # AC

DATA_START_ROW = 3

# ── WMI → brand key ───────────────────────────────────────────────────────────
WMI_TO_BRAND = {
    '1B3':'mopar','1B7':'mopar','1C3':'mopar','1C4':'mopar','1C6':'mopar',
    '1C8':'mopar','2C3':'mopar','2C4':'mopar','3C4':'mopar','3C6':'mopar',
    '1D3':'mopar','2D3':'mopar',
    '1FA':'ford','1FB':'ford','1FC':'ford','1FD':'ford','1FM':'ford',
    '1FT':'ford','2FM':'ford','2FT':'ford','3FA':'ford','3FE':'ford',
    '1G1':'gm','1G6':'gm','1GB':'gm','1GC':'gm','1GD':'gm','1GE':'gm',
    '1GF':'gm','1GK':'gm','1GN':'gm','1GS':'gm','1GT':'gm','1GW':'gm',
    '1GY':'gm','2G1':'gm','3G1':'gm','KL1':'gm','W04':'gm',
    '1HG':'honda','2HG':'honda','5FN':'honda','19U':'acura','JH4':'acura',
    '4T1':'toyota','4T3':'toyota','4T4':'toyota','5TD':'toyota','5TF':'toyota',
    '5TL':'toyota','5TM':'toyota','5TE':'toyota','JTD':'toyota','JTG':'toyota',
    'JTH':'lexus','JT6':'lexus','2T1':'toyota','2T2':'lexus',
    '1N4':'nissan','5N1':'nissan','3N1':'nissan','1N6':'nissan',
    'JN1':'nissan','JN8':'nissan','JNK':'infiniti',
    'KMH':'hyundai','KM8':'hyundai','5NM':'hyundai','5NP':'hyundai',
    'KNA':'kia','KND':'kia','5XX':'kia',
    'WBA':'bmw','WBX':'bmw','WBS':'bmw','5UX':'bmw','4US':'bmw',
    'WAU':'audi','WA1':'audi',
    'WVW':'vw','1VW':'vw','3VW':'vw',
    'WP0':'porsche','WP1':'porsche',
    'JM1':'mazda','JM3':'mazda','1YV':'mazda',
    '4S3':'subaru','JF1':'subaru','JF2':'subaru',
    'JA3':'mitsubishi','JA4':'mitsubishi','4A3':'mitsubishi',
    'SAJ':'jaguar','SAL':'landrover','SAR':'landrover',
    'YV1':'volvo','YV4':'volvo',
}

OEM_URLS = {
    'acura':'https://acura.oempartsonline.com',
    'audi':'https://audi.oempartsonline.com',
    'bmw':'https://bmw.oempartsonline.com',
    'ford':'https://ford.oempartsonline.com',
    'gm':'https://gm.oempartsonline.com',
    'honda':'https://honda.oempartsonline.com',
    'hyundai':'https://hyundai.oempartsonline.com',
    'infiniti':'https://infiniti.oempartsonline.com',
    'jaguar':'https://jaguar.oempartsonline.com',
    'kia':'https://kia.oempartsonline.com',
    'landrover':'https://landrover.oempartsonline.com',
    'lexus':'https://lexus.oempartsonline.com',
    'mazda':'https://mazda.oempartsonline.com',
    'mitsubishi':'https://mitsubishi.oempartsonline.com',
    'mopar':'https://mopar.oempartsonline.com',
    'nissan':'https://nissan.oempartsonline.com',
    'porsche':'https://porsche.oempartsonline.com',
    'subaru':'https://subaru.oempartsonline.com',
    'toyota':'https://toyota.oempartsonline.com',
    'vw':'https://vw.oempartsonline.com',
    'volvo':'https://volvo.oempartsonline.com',
}

VIN_RE = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$', re.I)

def find_vin(text):
    for t in re.split(r'[\s|,;]+', str(text).strip()):
        if VIN_RE.match(t): return t.upper()
    return None

def parse_price(text):
    m = re.search(r'\$([\d,]+\.?\d{0,2})', str(text).replace(' ',''))
    if m:
        try: return float(m.group(1).replace(',',''))
        except: pass
    return None

def parse_blocks(ws):
    blocks, cur = [], None
    for row in ws.iter_rows(min_row=DATA_START_ROW, values_only=False):
        val = row[COL_PARTE-1].value
        s   = str(val) if val else ''
        if '|' in s and find_vin(s):
            vin   = find_vin(s)
            brand = WMI_TO_BRAND.get(vin[:3]) if vin else None
            cot_m = re.search(r'COT[\.\s#]*(\w+)', s, re.I)
            cur = {'cot': cot_m.group(1) if cot_m else '?', 'vin': vin,
                   'brand': brand, 'base_url': OEM_URLS.get(brand), 'parts': []}
            blocks.append(cur)
        elif cur and val and isinstance(val, str) and len(val.strip()) > 3:
            already = len(row) > COL_OEM_MSRP-1 and row[COL_OEM_MSRP-1].value is not None
            cur['parts'].append({'row': row[0].row, 'parte': val.strip(),
                                 'desc': row[COL_DESC-1].value or '', 'done': already})
    return blocks

async def fetch_price(page, base_url, part_number, vin):
    r = {'msrp': None, 'price': None, 'vin_fits': 'N/A', 'url': ''}
    try:
        # Build search URL directly — avoids interacting with the search box
        # which is where anti-bot detection usually fires
        vin_param = f'&vin={vin}' if vin else ''
        search_url = f'{base_url}/oem-parts/search?query={part_number}{vin_param}'
        print(f'    GET {search_url}')

        await page.goto(search_url, wait_until='domcontentloaded', timeout=45_000)
        await page.wait_for_timeout(2500)   # let JS render
        r['url'] = page.url

        # If redirected to a single product page — great, parse it directly
        # If still on search results, click the first matching part link
        if '/oem-parts/search' in page.url or '/search' in page.url:
            try:
                # Try to click the first result that matches our part number
                link = page.locator(f'a[href*="{part_number.lower()}"], a[href*="{part_number.upper()}"]').first
                href = await link.get_attribute('href', timeout=5000)
                if href:
                    target = href if href.startswith('http') else base_url.rstrip('/') + href
                    await page.goto(target, wait_until='domcontentloaded', timeout=30_000)
                    await page.wait_for_timeout(2000)
                    r['url'] = page.url
                else:
                    # Click the first product link
                    first = page.locator('a[href*="oem-parts"]').first
                    await first.click(timeout=5000)
                    await page.wait_for_timeout(2000)
                    r['url'] = page.url
            except:
                pass

        html = await page.content()

        # ── MSRP ─────────────────────────────────────────────────────────────
        m = re.search(r'MSRP[\s\S]{0,30}\$([\d,]+\.?\d{0,2})', html, re.I)
        if m:
            r['msrp'] = float(m.group(1).replace(',', ''))

        # ── Sale / discounted price ───────────────────────────────────────────
        price_selectors = [
            '.price-now', '.sale-price', '.your-price',
            '[class*="price-sale"]', '[class*="sale_price"]',
            '.product-price strong', '.price strong',
            '[data-price]', '.add-to-cart-price',
        ]
        for sel in price_selectors:
            try:
                txt = await page.locator(sel).first.inner_text(timeout=2000)
                p = parse_price(txt)
                if p and p > 0:
                    r['price'] = p
                    break
            except:
                continue

        # Fallback: scrape all dollar amounts from HTML, pick the lowest that
        # isn't over MSRP (most likely the discounted price)
        if not r['price']:
            amounts = [float(x.replace(',', ''))
                       for x in re.findall(r'\$([\d,]+\.\d{2})', html)
                       if 0 < float(x.replace(',', '')) < 99_999]
            pts = sorted(set(amounts))
            if pts:
                if r['msrp']:
                    under = [p for p in pts if p <= r['msrp']]
                    r['price'] = min(under) if under else pts[0]
                else:
                    r['price'] = pts[0]

        # ── VIN fitment ───────────────────────────────────────────────────────
        if vin:
            try:
                body = (await page.inner_text('body')).lower()
                if any(x in body for x in ['does not fit', 'not compatible', 'does not match']):
                    r['vin_fits'] = 'NO'
                elif any(x in body for x in ['fits your', 'compatible with your', 'guaranteed fit', 'this part fits']):
                    r['vin_fits'] = 'YES'
                elif vin.lower() in body:
                    r['vin_fits'] = 'YES'
                else:
                    r['vin_fits'] = 'N/A'
            except:
                pass

    except PlaywrightTimeout:
        print('    TIMEOUT — site did not respond in 45 s')
    except Exception as e:
        print(f'    ERROR: {e}')
    return r

SCRIPT_DIR = Path(__file__).parent
EXCEL_FILE = SCRIPT_DIR / 'cotizacion_bulk.xlsm'
CSV_OUT    = SCRIPT_DIR / 'oem_results_temp.csv'

async def run(target_n, headless, process_all):
    print(f'Reading {EXCEL_FILE.name}...')
    wb = openpyxl.load_workbook(EXCEL_FILE, keep_vba=True, data_only=True)
    ws = wb['COTIZACION']

    blocks = parse_blocks(ws)
    if not blocks:
        print('No auction blocks found.'); return

    print(f'{len(blocks)} auction(s) found:')
    for i,b in enumerate(blocks,1):
        u = sum(1 for p in b['parts'] if not p['done'])
        print(f'   [{i}] COT {b["cot"]} | VIN {b["vin"]} | {b["brand"] or "?"} | {u} unpriced')

    if process_all:
        todo = [b for b in blocks if any(not p["done"] for p in b["parts"])]
    else:
        idx = len(blocks) - target_n
        todo = [blocks[idx]] if 0<=idx<len(blocks) else []

    if not todo:
        print('Nothing to process - all already priced.'); return

    total = sum(sum(1 for p in b['parts'] if not p['done']) for b in todo)
    print(f'\nFetching {total} part(s)...\n')

    results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-web-security',
            ])
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width':1280,'height':800},
            locale='en-US',
            timezone_id='America/New_York',
        )
        page = await ctx.new_page()
        if STEALTH:
            await stealth_async(page)
            print('Stealth mode active.')

        for block in todo:
            print(f'-- COT {block["cot"]} | {block["vin"]} | {block["base_url"] or "UNKNOWN"} --')
            if not block['base_url']:
                print(f'  WARNING: Unknown brand for WMI {block["vin"][:3] if block["vin"] else "?"}')
                continue
            parts_todo = [p for p in block['parts'] if not p['done']]
            for i, part in enumerate(parts_todo, 1):
                print(f'  [{i}/{len(parts_todo)}] {part["parte"]}  {part["desc"]}')
                r = await fetch_price(page, block['base_url'], part['parte'], block['vin'])
                results.append({
                    'row':      part['row'],
                    'parte':    part['parte'],
                    'msrp':     r['msrp']  if r['msrp']  is not None else '',
                    'precio':   r['price'] if r['price'] is not None else '',
                    'vin_fits': r['vin_fits'],
                    'url':      r['url'],
                })
                msrp_s  = '$'+str(r['msrp'])  if r['msrp']  else '-'
                price_s = '$'+str(r['price']) if r['price'] else '-'
                print(f'     MSRP: {msrp_s:>10}  Precio: {price_s:>10}  Fits: {r["vin_fits"]}')
        await browser.close()

    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['row','parte','msrp','precio','vin_fits','url'])
        w.writeheader()
        w.writerows(results)

    print(f'\nDone. Results written to {CSV_OUT.name}')
    print('Switch back to Excel - the macro will fill in the cells.')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--auction', type=int, default=1)
    ap.add_argument('--headless', action='store_true')
    ap.add_argument('--all', dest='all', action='store_true')
    args = ap.parse_args()
    asyncio.run(run(args.auction, args.headless, args.all))

if __name__ == '__main__':
    main()
