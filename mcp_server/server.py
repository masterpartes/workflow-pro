#!/usr/bin/env python3
"""
Masterpartes MCP Server — local edition
========================================
Calls oem_service / ebay_service / excel_writer directly in-process.
No Railway, no HTTP server, no API key required.

Credentials loaded from  workflow-pro/.env  at startup:
  EBAY_APP_ID, EBAY_CERT_ID  — eBay production keys
  (Inpart login handled by the browser bookmarklet — not needed here)
"""
import sys
import os
from pathlib import Path

# ── Repo paths ─────────────────────────────────────────────────────────────────
_REPO  = Path(__file__).resolve().parent.parent
_AGENT = _REPO / "agent"
_TOOLS = _REPO / "tools"

# Load credentials from .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO / ".env")
except ImportError:
    pass  # dotenv optional; env vars may already be set

# Make agent/ and tools/ importable
sys.path.insert(0, str(_AGENT))
sys.path.insert(0, str(_TOOLS))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Masterpartes")


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def check_health() -> dict:
    """
    Verify that local dependencies (oem_service, ebay_service) are importable
    and that the Excel workbook path exists.
    Call this first to confirm the local setup is working.
    """
    issues = []
    try:
        import oem_service  # noqa: F401
    except Exception as e:
        issues.append(f"oem_service: {e}")
    try:
        import ebay_service  # noqa: F401
    except Exception as e:
        issues.append(f"ebay_service: {e}")

    excel = _REPO / "cotizacion_bulk.xlsm"
    if not excel.exists():
        issues.append(f"Excel not found: {excel}")

    if not os.environ.get("EBAY_APP_ID"):
        issues.append("EBAY_APP_ID not set in .env")
    if not os.environ.get("EBAY_CERT_ID"):
        issues.append("EBAY_CERT_ID not set in .env")

    return {
        "status": "ok" if not issues else "degraded",
        "mode": "local",
        "issues": issues,
    }


@mcp.tool()
async def quote_parts(
    parts: list[dict],
    vin: str = "",
    brand: str = "",
    source: str = "auto",
    incluir_alterno: bool = False,
) -> dict:
    """
    Look up part prices. Three sources, chosen with `source`.

    Args:
        parts:  List of part dicts, each with:
                  "parte"       (str, required) - OEM part number
                  "descripcion" (str, optional)
        vin:    Vehicle VIN - identifies brand and checks fitment.
        brand:  Brand override when no VIN is available, e.g. "ford".
        source: "auto"     - routing by VIN/brand as always: the US OEM site for
                             the brand, PartSouq for unknown WMIs, eBay alongside.
                             This is the default and what runs when the user says
                             nothing.
                "partsouq" - force PartSouq, skipping the brand routing. Use it
                             when the user says "partsouq".
                "auvika"   - AVK (avkparts.lt), for European parts. Prices come
                             back in EUR, so quote_quito_cost needs currency="EUR"
                             AND freight_origin for the Vilnius->Miami leg.
                             Requires the AVK worker running in the owner's Chrome;
                             if it is not, this says so instead of hanging.
        incluir_alterno: with a forced source, also query eBay for the aftermarket
                             price. Ignored for "auvika", which publishes its own
                             aftermarket rows ("analogues").

    Returns the same shape as before plus `fuente` per part. For "auvika" each
    part also carries `ofertas` (every warehouse, cheapest first), `genuino`,
    `alterno` and `peso_kg` when AVK publishes it - a real weight, better than
    the statistical estimate.
    """
    src = (source or "auto").strip().lower()
    if src in ("avk", "auvika", "avkparts"):
        from avk_live import lookup_avk, AvkError
        numeros = [p.get("parte", "") if isinstance(p, dict) else str(p) for p in parts]
        try:
            res = await lookup_avk(numeros)
        except AvkError as e:
            return {"ok": False, "error": str(e), "fuente": "AVK"}
        if not res.get("ok"):
            return {"ok": False, "fuente": "AVK", **res}

        salida = []
        for p in parts:
            pn = p.get("parte", "") if isinstance(p, dict) else str(p)
            desc = p.get("descripcion", "") if isinstance(p, dict) else ""
            from avk_live import normalizar_oe
            info = res["partes"].get(normalizar_oe(pn), {})
            gen = info.get("genuino") or {}
            salida.append({
                "parte":       pn,
                "descripcion": desc,
                "price":       gen.get("price_eur"),
                "currency":    "EUR",
                "msrp":        None,
                "vin_fits":    "N/A",
                "url":         f"https://www.avkparts.lt/search/{normalizar_oe(pn)}",
                "error":       info.get("error"),
                "fuente":      "AVK avkparts.lt",
                "ofertas":     info.get("ofertas", []),
                "genuino":     info.get("genuino"),
                "alterno":     info.get("alterno"),
                "peso_kg":     info.get("peso_kg"),
            })
        priced = sum(1 for r in salida if r.get("price"))
        return {
            "ok": True, "parts": salida, "count": len(salida), "priced": priced,
            "fuente": "AVK avkparts.lt", "currency": "EUR",
            "nota": ("Precios en EUR y sin IVA. Para cotizar hace falta "
                     "freight_origin (tramo Vilnius->Miami)."),
        }

    if src in ("partsouq", "psq"):
        from oem_service import lookup_partsouq_only
        results = await lookup_partsouq_only(parts, brand=brand or None,
                                             incluir_ebay=incluir_alterno)
    else:
        from oem_service import lookup_parts
        results = await lookup_parts(parts, vin=vin or None, brand=brand or None)

    priced = sum(
        1 for r in results
        if r.get("price") or (r.get("ebay") and (
            r["ebay"].get("genuine_price") or r["ebay"].get("aftermarket_price")
        ))
    )
    return {
        "ok":     True,
        "parts":  results,
        "count":  len(results),
        "priced": priced,
        "vin":    vin,
        "brand":  brand,
        "fuente": "PartSouq" if src in ("partsouq", "psq") else "auto",
    }


@mcp.tool()
async def quote_quito_cost(
    part_price: float,
    tariff_pct: float = -1.0,
    weight_kg: float = 0.0,
    descripcion: str = "",
    currency: str = "USD",
    freight_origin: float = 0.0,
    freight_origin_currency: str = "EUR",
    margin_pct: float = 0.0,
) -> dict:
    """
    Calculate the landed cost in Quito for one part, with the full tax breakdown.

    Chain: FOB -> seguro -> flete declarado -> CIF -> advalorem -> FODINFA ->
    IVA aduana -> ISD -> courier/nacionalizacion -> PRECIO_UIO -> + flete de origen
    -> COSTO LANDED. Validated against customs declaration 0877-7841.

    The origin leg (e.g. Vilnius->Miami for AVK parts) is paid separately and is
    deliberately EXCLUDED from the customs valuation, but IS included in landed
    cost, and margin is taken on it.

    Args:
        part_price:   Supplier price of the part, in `currency`.
        weight_kg:    Peso REAL en kg. Miami->Quito factura peso real.
                      Si se omite (0), se estima desde `descripcion`.
        descripcion:  Descripcion de la parte, p.ej. "PARACHOQUES DEL.".
                      Se usa solo si weight_kg no viene. El resultado SIEMPRE
                      informa de donde salio el peso y con que confianza: hay
                      que MOSTRARLO al humano antes de enviar precio, para que
                      lo apruebe o lo corrija.
        tariff_pct:   Ad-valorem rate for the subpartida, e.g. 15 for 15%.
                      REQUIRED — resolve it first via the TariffCode lookup.
                      Never pass 0 to mean "unknown"; escalate to the owner instead.
        currency:     "USD" for US OEM / eBay parts, "EUR" for AVK parts.
        freight_origin: Origin-leg freight (Vilnius->Miami). 0 for US parts.
        freight_origin_currency: Currency of freight_origin, default "EUR".
        margin_pct:   Tier margin to apply, e.g. 35 for 35%. 0 = cost only.
                      Tiers: A 15/20 · B 15/35 · C 25/50 · D 15/50 (minimo/sugerido).

    Returns:
        landed_cost_usd, precio_sugerido_usd (when margin_pct given), the full
        breakdown, the FX rate used, and the cost_params values applied.
        `texto` is a ready-to-show Spanish breakdown for human approval.

    Raises an error rather than guessing if cost_params or the FX rate are
    unavailable — a confidently wrong price is worse than no price.
    """
    from shared.quito_cost import calculate_quito_cost, format_breakdown, CostEngineError
    from shared.part_weight import estimate_weight, describe, WeightLookupError

    from shared.tariff_lookup import lookup_detailed, TariffLookupError

    arancel_info = {"origen": "dado por el usuario", "arancel_pct": tariff_pct}
    if tariff_pct < 0:
        if not descripcion:
            return {"ok": False, "error":
                    "Falta el arancel. Pase tariff_pct, o descripcion para resolverlo."}
        try:
            t = lookup_detailed(descripcion)
        except TariffLookupError as e:
            return {"ok": False, "error": f"No se pudo resolver el arancel: {e}"}
        if not t["ok"]:
            return {"ok": False, "escalar": True,
                    "error": f"Arancel sin resolver: {t['nota']}",
                    "candidatos": t["candidatos"],
                    "texto": ("Arancel: SIN RESOLVER — " + t["nota"] +
                              " Indique la subpartida y el arancel.")}
        tariff_pct = t["arancel_pct"]
        arancel_info = {"origen": "resuelto", **t}

    peso_info = {"origen": "dado por el usuario", "peso_kg": weight_kg}
    if not weight_kg:
        if not descripcion:
            return {"ok": False, "error":
                    "Falta el peso. Pase weight_kg, o descripcion para estimarlo."}
        try:
            est = estimate_weight(descripcion)
        except WeightLookupError as e:
            return {"ok": False, "error": f"No se pudo estimar el peso: {e}"}
        if not est:
            return {"ok": False, "escalar": True,
                    "error": (f"Sin base para estimar el peso de '{descripcion}'. "
                              "Escale al dueno para que indique el peso real; "
                              "no se asume ningun valor por defecto."),
                    "texto": describe(None)}
        weight_kg = est["peso_kg"]
        peso_info = {"origen": "estimado", **est, "texto": describe(est)}

    try:
        result = calculate_quito_cost(
            part_price=part_price,
            weight_kg=weight_kg,
            tariff_pct=tariff_pct,
            currency=currency,
            freight_origin=freight_origin,
            freight_origin_currency=freight_origin_currency,
            margin_pct=margin_pct if margin_pct else None,
        )
    except CostEngineError as e:
        return {"error": str(e), "ok": False}

    result["ok"] = True
    result["peso"] = peso_info
    result["arancel"] = arancel_info
    if arancel_info.get("confianza") in ("media", "baja"):
        result["revisar_arancel"] = True
    # El peso va ARRIBA del desglose: es lo primero que el humano debe revisar,
    # porque mueve el flete courier y el flete declarado a la vez.
    cabecera = peso_info.get("texto") or f"Peso: {weight_kg:.2f} kg (dado)"
    if arancel_info.get("origen") == "resuelto":
        cabecera += (f"\nArancel: {tariff_pct:g}% — subpartida "
                     f"{arancel_info['subpartida']} (confianza "
                     f"{arancel_info['confianza']}, via {arancel_info['metodo']})")
    result["texto"] = cabecera + "\n" + format_breakdown(result)
    if peso_info.get("confianza") in ("media", "baja"):
        result["revisar_peso"] = True
    return result


@mcp.tool()
async def lookup_tariff(descripcion: str) -> dict:
    """
    Resolver la SUBPARTIDA y el ARANCEL de una parte a partir de su descripcion,
    contra la tabla TariffCode de Supabase.

    Devuelve subpartida, arancel_pct, confianza (alta/media/baja), el metodo
    (keyword o claude) y los candidatos considerados.

    Nunca devuelve 0% para decir "no se". Si la partida existe pero tiene el
    arancel vacio, o si la coincidencia es ambigua, devuelve ok:false con
    escalar:true — hay que preguntarle la subpartida al dueno. Un arancel
    equivocado baja el costo sin que nadie lo note: cada 10% de arancel son
    ~$19 sobre un CIF de $190.
    """
    from shared.tariff_lookup import lookup_detailed, TariffLookupError
    try:
        return lookup_detailed(descripcion)
    except TariffLookupError as e:
        return {"ok": False, "error": str(e), "escalar": True}


@mcp.tool()
async def estimate_part_weight(descripcion: str) -> dict:
    """
    Estimar el peso REAL de una parte a partir de su descripcion, para la pierna
    Miami->Quito (que se factura sobre peso real, no volumetrico).

    Derivado de 1.548 lineas reales de despacho. Coincide unicamente con el
    SUSTANTIVO PRINCIPAL de la descripcion: "CERRADURA DE PUERTA" es una
    cerradura, no una puerta.

    Devuelve peso_kg junto con n_muestras, dispersion y confianza (alta/media/baja).
    Si no hay base para estimar, devuelve ok:false con escalar:true — eso NO
    significa cero: significa que hay que preguntarle el peso al dueno.
    """
    from shared.part_weight import estimate_weight, describe, WeightLookupError
    try:
        est = estimate_weight(descripcion)
    except WeightLookupError as e:
        return {"ok": False, "error": str(e)}
    if not est:
        return {"ok": False, "escalar": True, "descripcion": descripcion,
                "texto": describe(None)}
    return {"ok": True, "descripcion": descripcion, **est, "texto": describe(est)}


@mcp.tool()
async def get_excel_parts(vin: str = "") -> dict:
    """
    Read all part rows from the open Excel quotation file (cotizacion_bulk.xlsm).

    Args:
        vin: If provided, return only parts under quotations with this VIN.

    Returns list of parts with their current tariff/price data so Claude can
    review what's in the workbook before calling quote_parts.
    """
    from shared.excel_writer import get_all_parts
    parts = get_all_parts(vin_filter=vin or None)
    return {"parts": parts, "count": len(parts)}


@mcp.tool()
async def generate_avk_list(vin: str = "") -> dict:
    """
    Generate the AVK bulk-search parts list for European-brand quotations
    (Mercedes-Benz, BMW, Audi, VW, Volvo, etc.).

    Reads parts from Excel, filters to European VINs, strips dashes/spaces
    from OE numbers, and writes to avk_parts_list.txt in the repo root.

    Args:
        vin: Limit to a specific VIN (optional — default processes all European parts).

    Returns:
        parts_list:   List of cleaned OE numbers (one per line, ready for AVK)
        file_path:    Where the list was saved
        count:        Number of parts
    """
    from shared.excel_writer import get_all_parts
    from shared.config import is_european_vin, AVK_LIST_FILE

    all_parts = get_all_parts(vin_filter=vin or None)
    avk = []
    for p in all_parts:
        if is_european_vin(p.get("vin") or ""):
            pn = p["parte"].replace(" ", "").replace("-", "").upper()
            if pn:
                avk.append(pn)

    if avk:
        AVK_LIST_FILE.write_text("\n".join(avk), encoding="utf-8")

    return {
        "parts_list": avk,
        "file_path":  str(AVK_LIST_FILE),
        "count":      len(avk),
    }


@mcp.tool()
async def inspect_db(tables: list[str] | None = None) -> dict:
    """
    READ-ONLY. Check which Supabase tables really exist as the anon key sees
    them: row count plus the column names of one sample row (empty tables show
    no columns). Use it before designing or writing anything, so tools are built
    against the database as it IS, not as a brief says it should be.

    Args:
        tables: table names to check. Default: every table the project uses or
                that a brief says should exist.
    """
    import httpx
    from shared.config import SUPABASE_URL, SUPABASE_ANON_KEY
    if not SUPABASE_ANON_KEY:
        return {"ok": False, "error": "SUPABASE_ANON_KEY no esta en .env"}
    names = tables or [
        "Order", "OrderItem", "Invoice", "Product", "TariffCode", "Tarea",
        "Quotation", "QuotationItem", "Client",
        "cost_params", "part_weight", "part_alias", "tariff_synonym", "tariff_synonyms",
        "avk_job", "avk_worker", "auvika_prices", "price_cache",
        "Embarque", "Gasto", "bot_log",
    ]
    h = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
         "Prefer": "count=exact"}
    out = {}
    async with httpx.AsyncClient(timeout=20) as c:
        for name in names:
            try:
                r = await c.get(f"{SUPABASE_URL}/rest/v1/{name}",
                                headers={**h, "Range": "0-0"}, params={"select": "*"})
            except Exception as e:  # noqa: BLE001
                out[name] = {"existe": None, "error": str(e)}
                continue
            if r.status_code in (200, 206):
                rng = r.headers.get("content-range", "")
                rows = r.json() or []
                out[name] = {"existe": True,
                             "filas": rng.split("/")[-1] if "/" in rng else "?",
                             "columnas": list(rows[0].keys()) if rows else []}
            else:
                try:
                    msg = r.json().get("message", r.text[:150])
                except Exception:  # noqa: BLE001
                    msg = r.text[:150]
                out[name] = {"existe": False, "http": r.status_code, "error": msg}
    return {"ok": True, "tablas": out,
            "nota": "existe:false = no existe o sin GRANT/policy para anon. "
                    "filas:0 con columnas:[] puede ser tambien RLS sin policy."}

@mcp.tool()
async def db_select(table: str, filters: dict | None = None, select: str = "*",
                    order: str = "", limit: int = 20) -> dict:
    """
    READ-ONLY. Read rows from a Supabase table (anon key, same access as the
    dashboard). For inspection and lookups: open orders, an order's items, etc.

    Args:
        table:   table name, e.g. "Order", "OrderItem".
        filters: PostgREST filters, e.g. {"estado": "eq.comprado",
                 "pedido_numero": "eq.142", "cliente": "ilike.*orgu*"}.
        select:  columns, default "*".
        order:   e.g. "created_date.desc".
        limit:   max rows (capped at 200).
    """
    import httpx
    from shared.config import SUPABASE_URL, SUPABASE_ANON_KEY
    if not SUPABASE_ANON_KEY:
        return {"ok": False, "error": "SUPABASE_ANON_KEY no esta en .env"}
    if not table.replace("_", "").isalnum():
        return {"ok": False, "error": "nombre de tabla invalido"}
    params = {"select": select, "limit": str(max(1, min(int(limit), 200)))}
    if order:
        params["order"] = order
    for k, v in (filters or {}).items():
        params[str(k)] = str(v)
    h = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
         "Prefer": "count=exact"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=h, params=params)
    if r.status_code not in (200, 206):
        return {"ok": False, "http": r.status_code, "error": r.text[:300]}
    rng = r.headers.get("content-range", "")
    return {"ok": True, "total": rng.split("/")[-1] if "/" in rng else None,
            "rows": r.json()}

# ── Operación de workflow-pro (escrituras) ─────────────────────────────────────
# Dos pasos siempre: confirmar=False → vista previa; confirmar=True → escribe.
# El bot muestra la vista previa y SOLO confirma después de un "sí" explícito.

def _uuid_like(x: str) -> bool:
    import re
    return bool(re.fullmatch(r"[0-9a-fA-F-]{36}", (x or "").strip()))


async def _resolver_pedido(c, pedido: str):
    """Devuelve (order, None) si hay uno solo; (None, candidatos) si no."""
    from shared.ops import select
    if _uuid_like(pedido):
        rows = await select(c, "Order", {"id": f"eq.{pedido.strip()}", "select": "*"})
        return (rows[0], None) if rows else (None, [])
    q = pedido.strip().replace(",", " ").replace("*", "")
    filtro = f"(numero_pedido.ilike.*{q}*,cliente.ilike.*{q}*,placa.ilike.*{q}*,notas.ilike.*{q}*)"
    rows = await select(c, "Order", {"or": filtro, "archivado": "is.false",
                                     "select": "*", "order": "fecha_pedido.desc", "limit": "10"})
    if len(rows) == 1:
        return rows[0], None
    return None, rows


@mcp.tool()
async def find_orders(texto: str = "", incluir_entregados: bool = False, limit: int = 15) -> dict:
    """
    READ-ONLY. Buscar pedidos activos (no archivados) por cliente, nombre del
    pedido, placa o notas (numero de pedido/solicitud del cliente), con sus items.
    texto vacio = los mas recientes. Usar antes de registrar entregas o compras
    para identificar el pedido correcto.
    """
    import httpx
    from shared.ops import select, OpsError
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            params = {"archivado": "is.false", "select": "*",
                      "order": "fecha_pedido.desc", "limit": str(min(limit, 50))}
            if texto.strip():
                q = texto.strip().replace(",", " ").replace("*", "")
                params["or"] = (f"(numero_pedido.ilike.*{q}*,cliente.ilike.*{q}*,"
                                f"placa.ilike.*{q}*,notas.ilike.*{q}*)")
            orders = await select(c, "Order", params)
            out = []
            for o in orders:
                items = await select(c, "OrderItem", {
                    "pedido_id": f"eq.{o['id']}",
                    "select": "id,producto_nombre,numero_parte,cantidad,estado,precio_compra,precio_venta,fecha_entrega_orden"})
                if not incluir_entregados and items and all(i["estado"] == "entregado" for i in items):
                    continue
                out.append({"id": o["id"], "pedido": o["numero_pedido"], "cliente": o["cliente"],
                            "fecha": o.get("fecha_pedido"), "placa": o.get("placa"),
                            "notas": o.get("notas"), "items": items})
        return {"ok": True, "count": len(out), "pedidos": out}
    except OpsError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
async def record_delivery(pedido: str, usuario: str, foto_path: str = "",
                          excluir: list[str] | None = None, fecha: str = "",
                          confirmar: bool = False) -> dict:
    """
    Registrar la ENTREGA al cliente de un pedido completo (una foto de
    comprobante = un pedido). Pueden usarlo Alejandro y Santiago.

    Args:
        pedido:    id del pedido, o texto para buscarlo (cliente, placa, nombre).
                   Si hay mas de un candidato devuelve la lista: pregunta cual.
        usuario:   quien manda el mensaje: "Alejandro" o "Santiago".
        foto_path: ruta local de la foto/PDF del comprobante que llego por Telegram.
        excluir:   items que NO llegaron (id o parte del nombre): "entregado menos X".
        fecha:     AAAA-MM-DD; por defecto hoy en Quito.
        confirmar: False = vista previa (mostrarla y esperar "si").
                   True  = escribir. Solo despues del "si" explicito.
    """
    import httpx, uuid as _u
    from shared.ops import (select, update, log, subir, validar_archivo,
                            usuario_valido, hoy_quito, OpsError)
    try:
        u = usuario_valido(usuario)
        f = fecha or hoy_quito()
        foto = validar_archivo(foto_path) if foto_path else None
        async with httpx.AsyncClient(timeout=60) as c:
            order, cands = await _resolver_pedido(c, pedido)
            if not order:
                return {"ok": False, "elegir": True,
                        "error": "No hay un unico pedido que coincida. Pregunta cual.",
                        "candidatos": [{"id": o["id"], "pedido": o["numero_pedido"],
                                        "cliente": o["cliente"], "placa": o.get("placa")}
                                       for o in (cands or [])]}
            items = await select(c, "OrderItem", {"pedido_id": f"eq.{order['id']}", "select": "*"})
            pend = [i for i in items if i["estado"] != "entregado"]
            ex = [e.lower() for e in (excluir or [])]
            fuera = [i for i in pend if i["id"] in (excluir or [])
                     or any(e in (i["producto_nombre"] or "").lower() for e in ex)]
            van = [i for i in pend if i not in fuera]
            if not van:
                return {"ok": False, "error": "Ese pedido no tiene items pendientes de entregar."}
            avisos = [f"{i['producto_nombre']} esta en '{i['estado']}', no en enviado/aduana"
                      for i in van if i["estado"] in ("adjudicado", "comprado")]
            linea = lambda i: f"  - {i['producto_nombre']} x{i['cantidad']:g}" if i.get("cantidad") else f"  - {i['producto_nombre']}"
            texto = (f"Entrega {order['numero_pedido']} — {order['cliente']}\n"
                     f"Fecha {f} · comprobante: {'si' if foto else 'NO'}\n"
                     + "\n".join(linea(i) for i in van)
                     + ("\nNo llegaron:\n" + "\n".join(linea(i) for i in fuera) if fuera else "")
                     + ("\n⚠ " + "\n⚠ ".join(avisos) if avisos else ""))
            if not confirmar:
                return {"ok": True, "vista_previa": True, "texto": texto + "\n¿Sí?",
                        "pedido_id": order["id"]}

            url = await subir(c, foto, "uploads", "entregas") if foto else None
            lote = _u.uuid4().hex
            for i in van:
                cambios = {"estado": "entregado", "fecha_entrega": f}
                if url:
                    cambios["prueba_entrega"] = url
                antes = {k: i.get(k) for k in cambios}
                await update(c, "OrderItem", i["id"], cambios)
                await log(c, u, "record_delivery", "OrderItem", i["id"], antes,
                          {**cambios, "_lote": lote})
        return {"ok": True, "escrito": True, "items": len(van),
                "texto": f"✓ Registrado: {len(van)} item(s) de {order['numero_pedido']} entregados."}
    except OpsError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
async def record_expense(usuario: str, monto_usd: float, categoria: str,
                         fecha: str = "", proveedor: str = "", ruc: str = "",
                         numero_doc: str = "", iva_usd: float = -1,
                         pedido: str = "", archivo_path: str = "", notas: str = "",
                         confirmar: bool = False) -> dict:
    """
    Registrar un GASTO del negocio a partir de un recibo/factura.

    Santiago: solo categorias transporte_local, combustible, cliente; queda
    'por_revisar' hasta que Alejandro lo apruebe. Alejandro: cualquier categoria
    (flete_origen, courier, aduana_declaracion, transporte_local, combustible,
    cliente, general), queda 'registrado'.

    Args:
        usuario:      "Alejandro" o "Santiago" (quien manda el mensaje).
        monto_usd:    TOTAL pagado, en USD. Leelo del recibo; si no se lee, pregunta.
        categoria:    ver arriba. Si no es obvio, pregunta.
        fecha:        AAAA-MM-DD del recibo; por defecto hoy en Quito.
        proveedor, ruc, numero_doc: del recibo si se leen. No inventar.
        iva_usd:      IVA del recibo si aparece; -1 = no aparece.
        pedido:       si el gasto es de un pedido concreto (ej. transporte de una
                      entrega), id o texto del pedido.
        archivo_path: ruta local de la foto/PDF del recibo que llego por Telegram.
        confirmar:    False = vista previa; True = escribir, solo tras "si".
    """
    import httpx, uuid as _u
    from shared.ops import (insert, log, subir, validar_archivo, usuario_valido,
                            hoy_quito, CATEGORIAS, CATEGORIAS_SANTIAGO, OpsError)
    try:
        u = usuario_valido(usuario)
        cat = (categoria or "").strip().lower().replace(" ", "_")
        if cat not in CATEGORIAS:
            raise OpsError(f"categoria '{categoria}' no valida. Opciones: {', '.join(CATEGORIAS)}")
        if u == "Santiago" and cat not in CATEGORIAS_SANTIAGO:
            raise OpsError(f"Santiago solo puede registrar: {', '.join(CATEGORIAS_SANTIAGO)}")
        if not monto_usd or monto_usd <= 0:
            raise OpsError("falta el monto (mayor a 0)")
        f = fecha or hoy_quito()
        arch = validar_archivo(archivo_path) if archivo_path else None
        estado = "por_revisar" if u == "Santiago" else "registrado"
        async with httpx.AsyncClient(timeout=60) as c:
            order = None
            if pedido:
                order, cands = await _resolver_pedido(c, pedido)
                if not order:
                    return {"ok": False, "elegir": True,
                            "error": "No hay un unico pedido que coincida. Pregunta cual.",
                            "candidatos": [{"id": o["id"], "pedido": o["numero_pedido"],
                                            "cliente": o["cliente"]} for o in (cands or [])]}
            texto = (f"Gasto {cat} · USD {monto_usd:,.2f}"
                     + (f" (IVA {iva_usd:,.2f})" if iva_usd >= 0 else "")
                     + f"\n{f} · {proveedor or 'proveedor ?'}"
                     + (f" · RUC {ruc}" if ruc else "") + (f" · doc {numero_doc}" if numero_doc else "")
                     + (f"\nPedido: {order['numero_pedido']}" if order else "")
                     + f"\nRecibo adjunto: {'si' if arch else 'NO'} · queda {estado}")
            if not confirmar:
                return {"ok": True, "vista_previa": True, "texto": texto + "\n¿Sí?"}

            ruta = await subir(c, arch, "documentos", f"gastos/{u.lower()}") if arch else None
            row = {"fecha": f, "monto_usd": round(float(monto_usd), 2), "categoria": cat,
                   "subido_por": u, "estado": estado,
                   "proveedor": proveedor or None, "ruc": ruc or None,
                   "numero_doc": numero_doc or None,
                   "iva_usd": round(float(iva_usd), 2) if iva_usd >= 0 else None,
                   "pedido_id": order["id"] if order else None,
                   "archivo_url": ruta, "notas": notas or None}
            g = await insert(c, "Gasto", row)
            await log(c, u, "record_expense", "Gasto", g["id"], None,
                      {**row, "_lote": _u.uuid4().hex})
        return {"ok": True, "escrito": True, "gasto_id": g["id"],
                "texto": f"✓ Gasto registrado ({estado}): {cat} USD {monto_usd:,.2f}"}
    except OpsError as e:
        return {"ok": False, "error": str(e)}


@mcp.tool()
async def undo_last(usuario: str, confirmar: bool = False) -> dict:
    """
    Deshacer la ULTIMA escritura de ese usuario (una entrega completa o un gasto).
    confirmar=False muestra que se va a deshacer; True lo deshace.
    Un gasto deshecho queda 'anulado' (no se borra).
    """
    import httpx
    from shared.ops import select, update, usuario_valido, OpsError
    try:
        u = usuario_valido(usuario)
        async with httpx.AsyncClient(timeout=30) as c:
            last = await select(c, "bot_log", {"usuario": f"eq.{u}", "deshecho": "is.false",
                                               "order": "created_date.desc", "limit": "1", "select": "*"})
            if not last:
                return {"ok": False, "error": "No hay nada para deshacer."}
            lote = (last[0].get("despues") or {}).get("_lote")
            filas = await select(c, "bot_log", {"usuario": f"eq.{u}", "deshecho": "is.false",
                                                "despues->>_lote": f"eq.{lote}", "select": "*"}) if lote else last
            texto = f"Deshacer {last[0]['tool']} ({len(filas)} fila(s)) del {last[0]['created_date'][:16]}"
            if not confirmar:
                return {"ok": True, "vista_previa": True, "texto": texto + "\n¿Sí?"}
            for r in filas:
                if r["tabla"] == "Gasto":
                    await update(c, "Gasto", r["fila_id"], {"estado": "anulado"})
                elif r["antes"]:
                    await update(c, r["tabla"], r["fila_id"], r["antes"])
                await update(c, "bot_log", r["id"], {"deshecho": True})
        return {"ok": True, "escrito": True, "texto": "✓ " + texto}
    except OpsError as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    mcp.run()
