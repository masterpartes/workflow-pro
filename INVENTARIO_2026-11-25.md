# Inventario — qué existe para buscar números y precios (25-nov-2026)

Leído del código (`workflow-pro`) y de Supabase, no de los handoffs.

## Números de parte por VIN

| Fuente | Dónde vive | Marcas | Estado |
|---|---|---|---|
| PartSouq catálogo | `tools/catalog_worker.js` (userscript) + `agent/catalog_live.py` + tool `buscar_numeros_vin` | Toyota, Lexus, Nissan, Mitsubishi, Honda (parcial), Hyundai/Kia, Mazda, Subaru | Funciona. Mapa de 17 tipos de pieza (faro, stop, parachoque, capó, guardafango, rejilla, espejo, parabrisas, puerta, moldura, radiador, condensador, suspensión, freno…). Lo que no cae en el mapa vuelve `sin_mapa`. Emparejado con 1 llamada Sonnet validada contra el diagrama. 2 de 7 trabajos fallaron con `vin_sin_catalogo` (X-Trail T32 2022, Lexus) |
| tascaparts (Ford US) | solo en la skill `masterpartes-cotizacion` §4 | Ford | Agente en navegador. Sin código |
| Partslink24 | solo en la skill §4 | Citroën/Peugeot/Renault/VW/BMW/Mitsubishi EU, Ford EU (FINIS) | Agente en navegador con la sesión del dueño. Sin código |
| mbpartsgiant | `oem_service._lookup_mercedes_playwright` (precio por número) + skill | Mercedes | Búsqueda por número, no por VIN |
| Tiendas OEM US por descripción / gemelo US | skill §4 | Nissan (Rogue), Ford (Escape) | Agente en navegador |
| eBay títulos | tool `ebay_por_descripcion` | Honda y genéricos | API, sin navegador |

## Precios

| Fuente | Dónde vive | Estado |
|---|---|---|
| Tiendas OEM US (price/MSRP) | `oem_service._PARTS_SITES` (ford, nissan, mopar, audi, bmw+alt, gm, honda, lexus, mitsubishi, toyota, vw, volvo) + 9 `oempartsonline` | httpx, sin navegador. Mazda y algunos `oempartsonline` piden Cloudflare |
| eBay genuino/alterno (+envío Miami) | `agent/ebay_service.py` | API oficial |
| PartSouq precio | `oem_service._fetch_partsouq` | **403 desde el MCP**. Solo funciona en el Chrome (skill o bookmarklet) |
| PartSouq precio + peso + envío | `partsouq_bookmarklet.html` v7 | Manual, **no está en el userscript** |
| AVK masivo | `tools/avk_worker.js` (userscript) + `agent/avk_live.py` | Funciona si la pestaña está viva (último latido 29-oct) |
| Costo Quito + sugerido | `quote_list`, `tools/shared/quito_cost.py`, `cost_params`, `TariffCode`, `part_weight`, `Client` (tiers) | Funciona. Recibe números, no VIN |
| Flete AVK por clase | `009_envio_clase.sql` | Escrita, **no aplicada** |

## Ingreso de pedidos

| Entrada | Dónde vive | Estado |
|---|---|---|
| Inpart (uso diario) | `inpart_bookmarklet.html` v11 → JSON al portapapeles | Funciona |
| Inpart Playwright | `agent/inpart_scraper.py`, `tools/scrape_inpart.py` → Excel | Legado (Excel) |
| SIPO Roundcube | solo en la skill §3 | Agente en navegador |
| Triage SIPO | `reglas_subastas.json` | Reglas del dueño |

## Hallazgos que cambian el diseño

1. **Las skills viven en claude.ai, no en la laptop.** Un agente lanzado por Santiago en la laptop (Claude Code `claude -p`) no las ve: hay que copiarlas a `C:\MasterPartesBot\.claude\skills\` y mantenerlas sincronizadas.
2. **Claude Code puede manejar el Chrome real** (`claude --chrome`, extensión Claude in Chrome, sesión con `/login` = suscripción Pro). Es el camino para que el agente de Santiago use Partslink24, tascaparts, Roundcube y PartSouq igual que el dueño. En Windows, dos sesiones con Chrome a la vez chocan (named pipe): cola, un trabajo por vez.
3. Fuera de PartSouq, la búsqueda por VIN es conocimiento de la skill + navegador, no código. Para Santiago eso significa agente con navegador, no un worker.
4. Merge pendiente: el bookmarklet PartSouq (precio/peso/envío) al userscript.
