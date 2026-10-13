# MASTER PARTES — BUILD BRIEF v2

**Date:** 13 Sep 2026 · **actualizado 20 Sep 2026**
**Supersedes:** `COWORK_BRIEF_MASTER_PARTES.md` (consolidated v1, 13-sep), `COWORK_BRIEF_costeo.md`, `BUILD_BRIEF.md`, `SESSION_SUMMARY.md`
**Machine:** Windows laptop `desktop-e14np2e` · `C:\Users\Juan Guerra\Desktop\workflow-pro` and `C:\MasterPartesBot`
**Working language:** this document and all build work in English. **The bot speaks Spanish to users.**

---

## 0. WHAT CHANGED SINCE v1 — READ THIS FIRST

v1 treated the Quito cost engine as the unknown blocker. It isn't. The engine has been fully
recovered from the workbook formulas and specified end to end (§3). What v1 got wrong, and what
this session corrected with the owner:

| v1 said | Reality |
|---|---|
| Cost engine is the blocker, needs discovery | Engine recovered in full; it is a ~1 session port |
| `TariffCode` table missing | **Wrong — it exists in Supabase** and `tools/shared/tariff_lookup.py` already queries it |
| Freight is 2 legs inside one chain | Two **separate** chains. Origin leg is outside the tax base entirely |
| Excel has the freight rates | Two of them are **stale** (declared freight, courier rate) and two lines are invented (fuel, x-ray). The trámite formula was correct |
| `HISTORICO` = real historical quotes | **Test rows** written while building. Not validation ground truth |
| Volumetric weight drives Miami→Quito | No — consolidation + Saturday volumetric exemption. Actual weight |
| AVK needs a login | AVK needs a **non-fingerprinted browser**. Login already exists in Chrome |
| Built-in Claude browser can do the scraping | **Cloudflare blocks it.** Only Claude-in-Chrome works (§5) |
| Excel's `PRECIO = UIO + margen − CREDITO_IVA` | The IVA credit is **not** deducted from the customer's price (§3.4) |
| Weight can come from the subpartida | **No.** A tariff code groups by customs class, not size: `8708.10.00.00` holds bumpers (5.9 kg) and bumper clips (0.27 kg) alike, spread 11.8x. Weight comes from the **description** (§4.6) |
| The €720 / 28.5 kg box was a bumper | It was a **mixed consignment**. 53 real bumpers run 3.4–18.6 kg, median 5.94. The reference case is "a 28.5 kg consignment", not "a bumper" |
| A long, well-reasoned `CLAUDE.md` makes a better bot | The opposite. A prompt full of rationale makes the model deliberate: 29s and four paragraphs of unasked-for audit. Rewritten as a procedure with a fixed template: 10s and four lines (§6.1) |

---

## 1. SECURITY — STILL OUTSTANDING

1. **Rotate the Inpart password.** `INPART_USERNAME=MX304177` / `INPART_PASSWORD` are in plaintext
   in `SESSION_SUMMARY.md`, which has now been uploaded into multiple chat sessions. Rotate it,
   then strip the credential block from that file. This has been outstanding since 01-sep.
2. Secrets (`INPART_*`, `EBAY_*`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_PASSWORD`) live only in
   local `.env`. Never in the repo, chat, Vercel frontend, or a context document.
3. `API_SECRET_KEY` and `EBAY_VERIFICATION_TOKEN` are both decommissioned — Railway is gone and the
   eBay exemption was granted 17-sep-2026 (§4.5). Delete both from `.env`.
4. Confirm `.env` is in `.gitignore`.

---

## 2. ENVIRONMENT FACTS ESTABLISHED THIS SESSION

- The `masterpartes` MCP server is reachable from a cloud Cowork session and answers
  `check_health` → `{"status":"ok","mode":"local"}`. Cloud sessions can drive it directly.
- **`device_bash` is broken.** A Windows update released 8 Sep 2026 stops the desktop workspace
  mounting connected folders (`no Plan9 drive shares mounted`). Staging and committing files still
  work; local Claude Code is unaffected. **Any laptop-side shell work must be done by a local
  Claude Code session, not from a cloud session.**
- `cotizacion_bulk.xlsm` is usually open in Excel, which locks it against write-back. Read freely;
  never plan to write to it.
- Folders granted to cloud sessions: `workflow-pro`, `C:\MasterPartesBot`.
- **Cloud sessions cannot reach Supabase.** The org egress policy denies `*.supabase.co`
  (proxy returns 403 on CONNECT). A cloud session can read and write repo files via
  stage/commit, but **cannot run or test anything that touches the database**. All Supabase
  work — schema changes, queries, and the Stage 1 acceptance test, which requires reading
  `cost_params` — must run from a **local Claude Code session** on the laptop, which reads
  `.env` directly.
- Never paste `.env` values into a chat session to work around the above (§1.2).
- **El plugin de Telegram tiene solo tools de SALIDA** (`reply`, `react`,
  `download_attachment`, `edit_message`). No hay tool de "recibir": los mensajes
  los inyecta el runtime de channels. Por eso `/mcp` sano no prueba nada sobre
  si el bot está escuchando (§9).
- **Supabase enables RLS on new tables and PostgREST then returns ZERO ROWS, not
  an error.** A table created without a read policy looks, to the app, exactly
  like an empty table. This cost an hour on `cost_params` (20-sep). **Every new
  table's migration must end with an `ENABLE ROW LEVEL SECURITY` + a
  `FOR SELECT TO anon` policy + a `GRANT SELECT`** — migrations 003 and 004 do.
- Restarting the MCP server is needed only when **Python files** change. Editing
  a row in `cost_params` or `part_weight` takes effect on the next call: the
  engine reads them at call time. Two server processes exist — the desktop app's
  and the bot session's — and both need restarting after a code change.

---

## 3. THE QUITO COST ENGINE — FULL SPECIFICATION

Two independent cost chains. The origin leg (Vilnius→Miami) is **paid separately and never enters
the Ecuadorian customs valuation**, but it is part of landed cost and margin is taken on it.

### 3.1 Chain

```
FOB            = part_price_eur × fx_eur_usd          # live ECB rate, NO buffer
INSURANCE      = 1% × FOB
FREIGHT_DECL   = $1.4458/kg × weight_kg                # what the forwarder declares to customs
CIF            = FOB + INSURANCE + FREIGHT_DECL        # ← customs value. Origin leg excluded.

ADVALOREM      = CIF × tariff_pct
FODINFA        = 0.5% × CIF
IVA_ADUANA     = 15% × (CIF + ADVALOREM + FODINFA)
TOTAL_ADUANA   = ADVALOREM + FODINFA + IVA_ADUANA

ISD            = 5% × (FOB + FREIGHT_ORIGIN)           # everything paid abroad.
                                                       # Miami→Quito is billed locally → NO ISD.

TOTAL_SIATI    = ($4.00/kg × weight_kg                  # courier, ALL-IN
                  + $30.00 × weight_kg / avg_kg_per_import)   # nacionalización, $30 per
                 × (1 + IVA)                           # DECLARATION, prorated by weight
               ≈ $5.586/kg including IVA

# FUEL 2.7% and RAYOS_X 1.7% are DELETED. They exist in the Excel but appear on no invoice.

PRECIO_UIO     = FOB + ISD + TOTAL_ADUANA + TOTAL_SIATI
LANDED         = PRECIO_UIO + FREIGHT_ORIGIN           # ← margin is taken on THIS
CREDITO_IVA    = IVA_ADUANA                            # recoverable, NOT deducted from price

PRECIO         = LANDED × (1 + margen_tier)            # tier table applied to landed cost
                                                       # see §3.4 on cash actually received
```

### 3.2 Parameters — all from a DB table, none hardcoded

| key | value | notes |
|---|---|---|
| `fx_eur_usd` | live | ECB reference, looked up at quote time. **No buffer** — risk is carried in margin |
| `insurance_pct` | 1.0 | |
| `freight_declared_usd_kg` | **1.4458** | measured from DAS 0877-7841. Was 4.00 in the Excel — it has moved since |
| `courier_usd_kg` | **4.00** | **all-in**, confirmed on the Panatlantic invoice. Was 3.70 |
| `nacionalizacion_usd_declaration` | **30.00** | per declaration. The courier splits into as many guías as it likes; the total is always $30 + IVA. **The Excel's `(30/35)` was correct** |
| `avg_kg_per_import` | **35** | the real typical shipment, several times a week. The 88 kg DAS was an outlier |
| ~~`fuel_pct`~~ ~~`xray_pct`~~ | **deleted** | modelled in the Excel, charged on no invoice |
| `iva_pct` | 15 | |
| `isd_pct` | 5 | applies to FOB + origin freight only |
| `fodinfa_pct` | 0.5 | |

**What was actually stale in the Excel:** only the two freight rates — declared freight ($4.00,
really $1.4458) and the courier rate ($3.70, really $4.00) — plus two invented lines (fuel, x-ray).
The trámite formula `(30/35) × peso × (1+IVA)` was **correct as written**. Net effect of the stale
constants was a small overstatement of landed cost, so historic quotes erred conservatively.

**Maintenance: recalibrate quarterly, not continuously.** These are a handful of rows in a table, so
recalibration means one person checking a recent refrendo and a recent forwarder invoice and editing
a few numbers — ten minutes, once a quarter. Do **not** build an ingestion pipeline for customs
declarations; the paperwork cost exceeds the accuracy gained, and a tool that needs feeding is a
tool that gets abandoned. The parameters live in a table precisely so recalibration never requires
a code change.

### 3.3 Worked example — the reference test case

A 28.5 kg consignment from Lithuania. Goods €300, origin freight €700, tariff 15%, FX 1.1592.

> **No lo llames "un parachoques".** 28,5 kg es el peso de una caja con varias
> piezas; un parachoques real pesa 5,94 kg de mediana (§4.6). Este caso sirve
> como prueba aritmética del motor, no como ejemplo de una pieza.

| line | USD |
|---|---|
| FOB | 347.76 |
| Flete declarado $1.4458/kg | 41.21 |
| CIF (customs value) | 392.44 |
| Total aduana | 128.82 |
| ISD 5% | 57.96 |
| SIATI (courier + nacionalización + IVA) | 159.19 |
| **PRECIO_UIO** | **693.73** |
| Flete Vilnius→Miami | 811.44 |
| **LANDED** | **1505.17** |

$1,505.17 landed is **the acceptance test for the cost engine port**. At a tier-B suggested 35%,
this part quotes at $2,031.98.

### 3.4 Pricing rule

```
PRECIO = LANDED × (1 + margen_tier)
```

Tier table as specified: **A 15/20 · B 15/35 · C 25/50 · D 15/50** (mínimo/sugerido). Applied
directly to landed cost. The customs IVA is recoverable but is **not** subtracted from the customer's
price — the Excel's old `− CREDITO_IVA` line is dropped.

Cash received ends up ~8.5% above the ex-IVA price once IVA and retentions settle, so the realised
margin runs above the tier markup. That headroom is deliberate and already reflected in the tier
percentages. Tighten the tiers later if the pricing proves uncompetitive; do not re-derive them from
realised margins.

### 3.5 VALIDATED against a real customs declaration

DAS `0877-7841` / entrega `08777841202600024960S`, 06-sep-2026, régimen 91 (tráfico postal
internacional), declarante Panatlantic Courier, UPS, Miami→Quito, 33 items, 88.35 kg.

| check | model | document |
|---|---|---|
| CIF = FOB + flete + seguro | 1903.78 | 1903.78 |
| seguro ÷ FOB | 1.000% | 0.998% |
| FODINFA = 0.5% × CIF | 9.52 | 9.54 |
| IVA = 15% × (CIF + ADV + FODINFA) | 313.24 | 313.26 |
| tributos = ADV + FODINFA + IVA | 497.78 | 497.78 |

**All 33 line items reconstruct to within 6 cents.** The tax chain is confirmed against customs
reality, not against the spreadsheet's own formulas. Freight is allocated across items strictly by
weight; insurance strictly by FOB. ISD does not appear on the DAS — it is a separate outbound-payment
tax, as modelled.

Real arancel rates observed, which **confirm the `TariffCode` table is legitimate** — chapter 8708
genuinely contains both dutiable and zero-rated sub-lines:

| subpartida | arancel |
|---|---|
| 8708.10.00 (parachoques) | 15% |
| 8708.29.20 (molduras) | 15% |
| 8708.91.00 (radiadores) | 10% |
| 8708.29.30 | **0%** |
| 8708.99.33 | **0%** |
| 7009.10.00 (espejos) | 20% |
| 7007.11.00 (parabrisas) | 7.5% |
| 8415.83.90 (condensador) | 5% |
| 3917.39.90, 8413.30.90, 8512.40.00, 9026.10.19 | 0% |

### 3.6 The courier side, validated against the forwarder's invoice

Panatlantic Courier invoice, 09-sep-2026, same shipment, total $440.91:

```
SERVICIOS COURIER        35.00 + 31.50 + 21.85 kg = 88.35 kg × $4.00 = $353.40
SERVICIO NACIONALIZACION              3 guías × $10.00              =  $30.00
                                                      SUBTOTAL        $383.40
                                                      IVA 15%          $57.51
                                                      TOTAL           $440.91
```

Reconciles exactly, and the billed weight matches the DAS weight. Conclusions:

- **$4.00/kg is all-in.** No fuel surcharge, no x-ray. Those Excel columns model charges that do
  not exist.
- **Nacionalización is $30 per declaration.** It appears here as 3 × $10 because the courier split
  the cargo into 3 guías, but the total always adds up to $30 + IVA however many boxes they use.
  The Excel's original `(30/35) × peso × (1+IVA)` was therefore **correct** — $30 per declaration
  over a 35 kg typical shipment. Only the two freight rates had gone stale.
- Effective all-in rate for quoting: **$5.586/kg including IVA.**

### 3.7 Signature

```python
def calculate_quito_cost(
    part_price_eur: float,
    freight_origin_eur: float,
    weight_kg: float,
    tariff_pct: float,
    *,
    params: dict,          # loaded from DB, never literals
    fx_eur_usd: float,     # looked up live at call time
) -> dict:
    """Returns every intermediate line, not just the total.
    The breakdown is shown to the human before approval — it is not optional."""
```

---

## 4. PRICE SOURCES — ROUTING AND SELECTION

### 4.1 Routing rule (simpler than v1's `is_european()`)

**The trigger for AVK is the absence of a US OEM price, not the brand.** If a US OEM site has no
price, the part is for a vehicle not sold in the US, which means a European brand, which means AVK.
This is empirical and does not depend on VIN/WMI guessing.

Order: US OEM site → eBay (comparison) → AVK if no US OEM price → PartSouq → cache.

### 4.2 AVK selection rule

AVK returns many offers per part from different warehouses, genuine and aftermarket. The bot quotes
**two lines per part**:

1. **Genuine** — the express warehouse, or the cheaper original if the lead-time difference doesn't matter.
2. **Aftermarket** — the best aftermarket offer.

Genuine is identified by manufacturer-group supplier codes (`PSA`, `FCA`, `VAG`, `BMW`, `MERCEDES`,
`VOLVO`, `JLR`, `OPEL/PSA`), not by the words OEM/ORIGINAL/GENUINE. Independent brands (TYC, DEPOT,
AYFAR, L-SERIES) are aftermarket. This logic already exists in `excel_writer.fill_avk_prices()`.

### 4.3 Origin freight

Stored as a **EUR value per (category, origin)** — e.g. bumper/Lithuania ≈ €700. Not computed per
part from dimensions: parts are consolidated at AVK's warehouse and only ship once a large box is
full, so shipment economics are always "large box" and small variations don't move a quote whose
margin is 30%+. Seed the table from real DHL invoices.

Reference data point: 28.5 kg actual, 170×62×54 cm, €720 → 113.8 kg chargeable at divisor 5000 →
**€6.33/kg**. One more invoice with a different shape-to-weight ratio would pin divisor and rate
independently.

### 4.4 FX

Live ECB rate at quote time, no buffer. Risk is carried in the margin, not the FX. Actual FX is
unknown at quote time because payment happens before shipping.

---

### 4.5 eBay API compliance — RESOLVED 17-sep-2026

On 17-sep-2026 eBay warned that the app's **marketplace account deletion/closure notification
endpoint** is down: it still points at `https://workflow-pro-production-13ab.up.railway.app/ebay/marketplace-deletion`,
dead since Railway was dropped. Failure to fix within 30 days deactivates the production API keys —
which would remove eBay as a price source entirely.

**Resolved: exemption granted the same day.** eBay confirmed "Exemption has been granted to your
keyset for Marketplace Account Deletion notifications", and the endpoint and verification-token
fields were removed from the configuration form entirely — so no stale Railway URL remains on file.
Developer account: `alejandroguerrapaez`, production keyset.

The declaration made was **"I do not persist eBay data"**. This is accurate for this
application: `agent/ebay_service.py` authenticates with the **application-scope** client-credentials
token (`https://api.ebay.com/oauth/api_scope`) against the Browse API only. There is no user-consent
flow, and the stored fields are price, currency, item URL and a title-derived genuine/aftermarket
classification. No `username`, `userId` or `eiasToken` is ever requested or retained.

Path taken, for the record: developer.ebay.com → **Application Keys** → **Notifications** →
**Alerts & Notifications** → **Marketplace Account Deletion** → toggle **"Exempted from Marketplace
Account Deletion"** On → exemption reason **"I do not persist eBay data"** → submit.

**If the exemption is ever withdrawn**, `agent/ebay_service.py` still contains
`compute_deletion_challenge_response()` — `SHA256(challenge_code + verification_token + endpoint)`,
hex, which matches eBay's spec. Serve it from a Vercel serverless function under `api/` (the repo
already deploys to Vercel), never from another host that can die unnoticed the way Railway did.

**`EBAY_VERIFICATION_TOKEN` is now genuinely retired** — delete it from `.env`. The value was also
exposed in a screenshot on 17-sep, so do not reuse it if an endpoint is ever reinstated.

---

### 4.6 Peso de la parte — RESUELTO 20-sep-2026 (Miami→Quito)

La pierna Miami→Quito se factura sobre **peso real**. `part_weight` + `part_alias`
(migración 004) estiman ese peso desde la **descripción**.

Construido con 1.548 líneas reales de `DESPACHO MASTERPARTES.xlsx`, filtradas a
aquellas cuyo peso por ítem cuadra con el total de su embarque — 27 bloques (240
ítems) se descartaron porque el total venía metido en una fila de ítem.

**Se usa mediana, no promedio**, y la clave es el **sustantivo principal**.

> **El error que esto evita.** Una primera versión hacía coincidir cualquier
> palabra de la descripción y subía la cobertura de 31% a 62% — a costa de darle
> a `CERRADURA DE PUERTA` los 30 kg de una puerta y a `PLATINA DE ESPEJO` el peso
> del espejo. En español el núcleo va primero: casar el modificador produce
> errores de 50x, sistemáticamente hacia arriba. Cobertura menor y correcta le
> gana a cobertura mayor y equivocada.

Tres niveles de confianza, porque el humano aprueba el peso antes de que salga
el precio:

| nivel | criterio | cobertura sobre cotizaciones reales |
|---|---|---|
| alta | n≥4 y dispersión p75/p25 ≤ 2.5 | 25% |
| media | n≥3 y dispersión ≤ 3.5 | 7% |
| baja | n≥2 y dispersión ≤ 8 | 23% (se muestra marcada) |
| sin dato | — | 45% → **escala, no asume nada** |

250 claves (120 de una palabra, 130 de dos) + 16 alias de abreviaturas.
`REJILLA` sola es dispersa; `REJILLA FRONTAL` no. `TAPA` se dispersa 11.9x y no
se usa sola nunca.

**Recalibrar:** dejar un despacho más nuevo en `workflow-pro` y regenerar. Eso
amplía la cobertura sin tocar código.

**Esto NO resuelve la pierna origen→Miami.** Ese flete es por embarque y lo manda
el tamaño volumétrico, no el peso real. Para partes de eBay ya está disponible
(§4.7); para AVK sigue abierto.

### 4.7 Flete origen→Miami — parcialmente resuelto

Cada parte tiene un costo de envío **hasta la bodega de Miami**, distinto según
de dónde venga. Es independiente del flete consolidado Miami→Quito.

- **eBay: ya se captura.** `search_part` filtra a artículos que envían a Miami FL
  33195, `_shipping_cost()` toma la opción más barata y `_bucket_stats` devuelve
  `total_min` = precio + envío. Falta solamente **pasarlo** al motor como
  `freight_origin` con `freight_origin_currency: "USD"`.
- **Sitios OEM de EE.UU.:** probablemente igual; sin verificar.
- **AVK / Lituania: abierto.** Un solo dato (caja mixta de €720) no permite
  derivar nada. Hacen falta 2–3 facturas DHL con el contenido de cada caja.

**Pendiente de confirmar con el dueño:** si el forwarder declara a la aduana el
FOB que se le pagó al vendedor, o el valor incluyendo llevarlo a Miami. Eso
decide si el envío de EE.UU. va en `freight_origin` (solo ISD) o dentro de
`part_price` (además tributa vía CIF).

## 5. AVK ACCESS — TESTED, WITH A HARD CONSTRAINT

**Verified working this session:**

- `https://www.avkparts.lt/search/<code>` is directly addressable and returns the full supplier table.
- A plain `fetch()` from an authenticated page returns parseable HTML — **no UI driving needed**, so
  a 20-part list resolves in seconds rather than 20 page loads.
- Existing selectors still parse: `.item`, `.column_provider`, `.column_price_no_tax`,
  `.column_price_with_tax`. Lead time is in the row.
- Live results confirmed: `11427566327` → BMW €7.60 net / €9.20 gross, 5–15 d.d.; BMW EXPRESS BE
  €8.21 / €9.93, 3–5 d.d. `34116794300` → BMW €80.29 / €97.15.

**The constraint:** this worked only through **Claude-in-Chrome using the owner's real Chrome
profile**, already signed in as `gerencia@azureus.ec`. The built-in Claude browser pane was
fingerprinted by Cloudflare and refused — looping challenges, `cf_chl_rc_ni` retry counter, never a
`cf_clearance`. Clicking through does not fix it.

**Consequences:**

- Chrome must be running with the extension while the owner is away. This joins "laptop on" in the
  startup checklist (§8).
- Do not attempt to solve the Cloudflare challenge programmatically. It is an arms race with a site
  that has decided it doesn't want automated clients.
- Two Mercedes-format codes (`4477600060`, `A0009938003`) returned nothing. Code normalisation needs
  work before this is trusted.

**Do not revisit the bulk CSV path.** The 301 MB / 7.5M-row `auvika_prices_combined.csv` (dated
16-jul-2026) and its Supabase loader exist in `auvika_csvs/`, but queries at that scale took 30+
minutes and the approach was abandoned. AVK is queried live, as intended.

---

## 6. ARCHITECTURE — THE BOUNDARY THAT MATTERS

The Telegram bot must **never drive the browser directly.**

Telegram input is untrusted. Santiago forwards client messages; clients paste arbitrary text. If
that text reaches an agent driving a browser logged into the owner's AVK, Inpart and eBay accounts,
a prompt injection has hands on those accounts. The existing `deny` list in
`C:\MasterPartesBot\.claude\settings.json` stays exactly as it is.

```
Telegram (allowlist: owner + Santiago)
   │  structured request only: part number, brand, VIN, client
   ▼
Bot session (Claude Code Channels, locked down — no Bash/Write/Edit/WebFetch)
   │  writes a lookup job row
   ▼
Supabase  ── price_cache / job queue ──┐
   ▲                                   │
   │  writes price + source + link      │ reads job
   │                                   ▼
Price worker (has browser access, never reads Telegram text)
   │
   ▼
AVK via Chrome · OEM scrapers · eBay API · PartSouq
```

The bot answers instantly from cache and escalates on a miss, instead of hanging 90 seconds on a
scrape. The worker only ever sees a part number.

**Open decision — who is the worker.** Three options, in increasing robustness:

- **(a) A Claude session with Chrome access** handles lookups on demand. Simplest, no new code, but
  needs a Claude session alive and costs a turn per lookup.
- **(b) A Chrome userscript/extension** polls the job queue from inside the owner's logged-in Chrome,
  does the `fetch()` calls, writes results back to Supabase. No Cloudflare problem (it *is* the real
  browser), no Claude in the loop, works unattended while Chrome is open. This is the natural
  evolution of the existing bookmarklet.
- **(c) Playwright with a persistent profile** — likely to hit the same fingerprinting wall as the
  built-in pane. Not recommended.

**Recommendation: (a) to bootstrap, (b) as the target.**

---

### 6.1 El prompt del bot es parte del diseño, no documentación

`C:\MasterPartesBot\CLAUDE.md` se reescribió dos veces el 20-sep y la lección
generaliza:

- **Un prompt lleno de razones hace que el modelo razone.** La primera versión
  explicaba el porqué de cada regla: 29 segundos y cuatro párrafos de auditoría
  no pedida por cada cotización.
- **Lo que la herramienta ya impone, no se repite en el prompt.** La herramienta
  se niega sin peso, sin arancel y sin parámetros. El prompt solo retransmite.
- **Una plantilla literal de salida** se rellena; una instrucción en prosa se
  compone. Ahí estaba la mayor parte del tiempo.
- **Las advertencias son condicionales**, con una lista explícita de cuándo
  aplican y una orden de cierre: si no aplica ninguna, no agregues nada. Un bot
  que advierte siempre enseña a ignorar las advertencias.
- **Cotizar es el camino corto; todo lo demás no.** Registrar pedidos, procesar
  facturas y analizar necesitan el trabajo que haga falta — la instrucción de
  brevedad se limita explícitamente a cotizar.

Resultado: 109 → 65 líneas, 29s → 10s, y la salida es cuatro líneas (FOB+fuente,
peso estimado, landed, sugerido). El desglose completo sale con `desglose`.

## 7. BUILD PLAN

Each stage is independently useful and independently testable.

### Stage 1 — Cost engine → MCP tool ✅ EN PRODUCCIÓN (20-sep-2026)
- `cost_params` table in Supabase, seeded from §3.2. No literals in code.
- `calculate_quito_cost()` in `workflow-pro`, returning the full breakdown.
- New tool on the existing FastMCP server (`mcp_server/server.py`), same pattern as `quote_parts`.
- **Acceptance:** reproduce §3.3 al centavo; todo parámetro se lee de la DB.
- **Verificado en vivo 20-sep:** $1.490,00 con FX 1,1460 del BCE (la referencia
  usa 1,1592; la diferencia de $15,17 es exactamente el movimiento del euro).
- **Deploy note:** the MCP server must restart and the bot session must reconnect before the new
  tool is visible. Include that in the step.

### Stage 2 — Tariff lookup: exponerlo como tool, y endurecerlo  🎯 SIGUIENTE

**Hueco descubierto el 20-sep:** `tools/shared/tariff_lookup.py` existe pero **no
está expuesto como tool MCP**. El bot no puede resolver una subpartida: hay que
dictarle el arancel en cada pedido. Es el último dato manual que queda en una
cotización de rutina — con peso y arancel automáticos, cotizar es
descripción + precio + cliente.

**The table already exists.** Supabase `TariffCode` holds `subpartida`, `arancel`,
`descripcion_referencial`, and `tools/shared/tariff_lookup.py` resolves a part description against
it — keyword scoring, with a Claude Haiku call to disambiguate the top 5. `enrich_excel.py` and
`import_manual.py` both use it. The cost engine calls this, it does not reimplement it.

Two defects make it unsafe for unattended quoting:

1. `float(best.get("arancel", 0) or 0)` — **a null `arancel` silently becomes 0%**, removing the
   duty from the quote with no warning. Audit the table for nulls; 24 of the 43 codes seen in
   `HISTORICO` carried 0, and it is not yet known how many are genuine zero-rates.
2. When scoring is ambiguous and the Claude call fails or declines, it falls through to `top[0]`
   with no indication that it guessed. In the Excel flow a human saw the orange cell; a bot has no
   such signal.

Work: return a confidence level and the candidates considered alongside the result; make a null
`arancel` an explicit error rather than a zero; escalate low-confidence matches to the owner instead
of quoting through them.

- **Acceptance:** a confident match resolves with no human input; an ambiguous or null-arancel match
  escalates and never produces a price.
- The 43 conflict-free `subpartida → arancel` pairs extracted from `HISTORICO` are useful as a
  **regression set** for the lookup, not as a replacement table.

### Stage 3 — Peso ✅ HECHO (§4.6) · flete de origen ⏳ parcial (§4.7)
- `freight_origin` table: `(category, origin) → eur`, seeded from real DHL invoices, each row
  carrying the source shipment (dims, actual kg, chargeable kg, invoice total) so it is auditable.
- **Acceptance:** bumper/Lithuania returns ≈ €700.

### Stage 4 — AVK live lookup
- Worker per §6. Code normalisation for Mercedes-format numbers.
- Returns two lines per part (§4.2) with price, supplier, lead time, and source URL.
- Writes to `price_cache` with timestamp and provenance.
- **Acceptance:** a list of 10 European codes resolves in one pass; every price carries a citable source.

### Stage 5 — Price resolution policy
- Implements §4.1 ordering. Live FX per §4.4.
- **Acceptance:** for any part the bot states which source it used and why the others were skipped.

### Stage 6 — Margin, tiers, approval
- Tier table **as specified**: A 15/20 · B 15/35 · C 25/50 · D 15/50 (mínimo/sugerido), applied
  directly to landed cost. These already account for the cash headroom described in §3.4.
- Quoting formula: `precio = landed × (1 + margen_tier)`.
- MSRP cap, escalation rules (new client, dangerous part, amount threshold).
- Approval flow: `OK` / `m=XX` / `no`. No price leaves without explicit approval.
- **Acceptance:** an unapproved quote never produces client-facing text.

### Stage 7 — Supabase writes + order creation  ← lo que el dueño quiere después

El bot alimentando el workflow cuando una parte se negocia, y la ingesta de
facturas. **Perfil de riesgo distinto al de todo lo anterior:** el camino de
lectura solo puede equivocarse; el de escritura puede corromper registros de los
que depende el dashboard. Revisar el esquema real de `Order`/`OrderItem` antes de
escribir nada.
- `Quotation` / `QuotationItem` writes on approval; order appears in the Vercel dashboard.
- `outcome` field on `QuotationItem` from day one (sold / no answer / rejected) — without it there is
  nothing for the learning layer to learn from later.

### Stage 8 — Output formats
- Proforma (client-facing, no costs/margins/sources) and auction list (compact, paste-ready).
- Requires the auction site's exact field order and separator — still unknown.

### Deliberately last
- **PartSouq Playwright worker.** Most fragile component; nothing may depend on it. Falls back to
  `price_cache` + the manual v7 bookmarklet.

---

## 8. OPEN ITEMS

**Needs a decision or data from the owner:**

- ~~$4/kg all-in or plus recargos~~ — **resolved**: all-in, per the Panatlantic invoice of
  09-sep-2026. Fuel and x-ray deleted from the model.
- ~~Trámite allocation~~ — **resolved**: $30 per declaration, prorated by weight over 35 kg.
- ~~`avg_kg_per_import`~~ — **resolved**: stays at 35 kg. The 88 kg declaration was atypical.
- Tier margin table (A/B/C/D) — from the historical invoice analysis.
- 3–4 DHL invoices across shapes (bumper, mirror, headlight, brake disc) to seed §4.3 and pin the
  volumetric divisor.
- Auction site field order, separator, and whether it accepts bulk paste.
- Proforma fixed text: validity, delivery time, payment terms, letterhead, chat text vs PDF.
- MSRP discount %, dangerous/fragile surcharges, escalation threshold by amount.

**Known unknowns in the build:**

- Mercedes-format code normalisation for AVK.
- Whether the Vercel dashboard's order tables need fields the bot doesn't yet capture.

---

## 9. STARTUP CHECKLIST (owner, before leaving)

1. Laptop on AC, sleep disabled, lid-close does nothing.
2. **Chrome running with the Claude extension** — required for AVK (§5).
3. ~~Start the MCP server~~ — innecesario. `.mcp.json` lo declara como servidor
   stdio, así que la sesión lo arranca sola.
4. Abrir la sesión **con el flag de canales**, desde `C:\MasterPartesBot`:

   ```
   claude --channels plugin:telegram@claude-plugins-official
   ```

   > **ESTO ES LO QUE ROMPE EL BOT SI SE OLVIDA.** Arrancar `claude` a secas
   > carga las *tools* del plugin de Telegram — `/mcp` muestra
   > `plugin:telegram:telegram · connected · 4 tools` y todo parece sano — pero
   > **no arranca el poller**. Los mensajes nunca llegan a la sesión. Telegram
   > muestra los tildes de entregado, el terminal no muestra nada, y el bot
   > queda mudo sin un solo error en ningún lado.
   >
   > De la documentación: *"Being in `.mcp.json` isn't enough to push messages:
   > a server also has to be named in `--channels`."*
   >
   > El flag **no aparece en `claude --help`** (research preview), así que no se
   > descubre explorando la CLI. Diagnosticarlo costó una hora el 21-sep-2026.
   >
   > Al arrancar bien, el banner dice: *"Channels (experimental) messages from
   > plugin:telegram@claude-plugins-official inject directly…"*. Si ese renglón
   > no está, el canal no está corriendo.

5. Enviar `/ping` desde Telegram y confirmar la respuesta. Un mensaje entrante
   se ve en el terminal como `← telegram · <chat_id>: <texto>`.

**Requisitos del canal:** los plugins de canal son scripts de **Bun**. Si el
canal no arranca, verificar `bun --version`.

The watchdog **alerts, it does not revive.** The bot session is interactive; if it dies nobody can
restart it until the owner returns. `/ping` is how Santiago distinguishes "down" from "ignoring me".
Declared fallback when it's down: manual bookmarklet, or wait.

---

## 10. DO NOT TOUCH

- `partsouq_scraper` — fixed previously, working.
- `tools/shared/excel_writer.py`, `tools/enrich_excel.py` — no changes needed.
- The `deny` list in `C:\MasterPartesBot\.claude\settings.json` — **never relax it**, including to
  give the bot browser access (§6).
- `cotizacion_bulk.xlsm` — read-only, usually locked by Excel.
