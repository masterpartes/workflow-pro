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

from typing import Optional
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
    from shared.ops import select, update, delete, usuario_valido, OpsError
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
            filas = sorted(filas, key=lambda r: r["tabla"] == "Order")
            for r in filas:
                if r["tabla"] == "Gasto":
                    await update(c, "Gasto", r["fila_id"], {"estado": "anulado"})
                elif r["antes"] is None and r["tabla"] in ("Order", "OrderItem"):
                    await delete(c, r["tabla"], r["fila_id"])
                elif r["antes"]:
                    await update(c, r["tabla"], r["fila_id"], r["antes"])
                await update(c, "bot_log", r["id"], {"deshecho": True})
        return {"ok": True, "escrito": True, "texto": "✓ " + texto}
    except OpsError as e:
        return {"ok": False, "error": str(e)}

# ── Cotizar una lista completa en una llamada ──────────────────────────────────

async def _tier_cliente(cliente: str) -> Optional[dict]:
    """Busca el cliente en la tabla Client: nombre contenido en el texto dado."""
    import httpx
    from shared.ops import select
    txt = (cliente or "").upper()
    if not txt:
        return None
    async with httpx.AsyncClient(timeout=15) as c:
        rows = await select(c, "Client", {"select": "nombre,tier,margen_min,margen_sugerido"})
    hits = [r for r in rows if r["nombre"] and r["nombre"].upper() in txt]
    hits.sort(key=lambda r: -len(r["nombre"]))  # el nombre más largo gana
    return hits[0] if hits else None


def _marca_por_numero(partes: list[str]) -> str:
    """Ford: 4to caracter 'Z' (8L8Z-..., NL1Z-..., BL8Z...). Solo si TODAS coinciden."""
    import re
    limpias = [re.sub(r"[^A-Z0-9]", "", (x or "").upper()) for x in partes if x]
    if limpias and all(re.match(r"^[A-Z0-9]{3}Z[A-Z0-9]{4,}", x) for x in limpias):
        return "ford"
    return ""


_PESO_FALLBACK: Optional[float] = None


def _peso_conservador() -> float:
    """Percentil 75 de los pesos reales de despacho (tabla part_weight).
    Se usa SOLO cuando no hay base para estimar, y se marca como supuesto."""
    global _PESO_FALLBACK
    if _PESO_FALLBACK is None:
        from shared.part_weight import _fetch
        pesos = sorted(float(r["peso_kg"]) for r in _fetch("part_weight", "peso_kg")
                       if r.get("peso_kg"))
        _PESO_FALLBACK = round(pesos[int(len(pesos) * 0.75)], 2) if pesos else 3.0
    return _PESO_FALLBACK


async def _tier_por_defecto() -> dict:
    """Sin cliente: se cotiza con tier B (el más común) y se marca en el encabezado."""
    import httpx
    from shared.ops import select
    async with httpx.AsyncClient(timeout=15) as c:
        rows = await select(c, "Client", {"tier": "eq.B", "limit": "1",
                                          "select": "tier,margen_min,margen_sugerido"})
    r = rows[0] if rows else {"tier": "B", "margen_min": 15, "margen_sugerido": 35}
    return {"nombre": None, **r}


@mcp.tool()
async def quote_list(parts: list[dict], cliente: str = "", vin: str = "", brand: str = "",
                     source: str = "auto", precio: str = "auto",
                     margin_pct: float = -1, freight_origin_eur: float = 0.0) -> dict:
    """
    COTIZAR UNA LISTA COMPLETA EN UNA SOLA LLAMADA. Usar SIEMPRE para cotizar
    (1 o más partes) en vez de quote_parts + quote_quito_cost por separado.

    Busca precio (OEM/eBay/PartSouq/AVK), resuelve arancel y peso, calcula el
    costo landed, aplica el margen sugerido del tier del cliente (tabla Client)
    y devuelve la TABLA INTERNA YA ARMADA (`tabla`): mandala tal cual, en
    MarkdownV2, sin tocarla.

    Args:
        parts:  [{"parte": "8L8Z78101A88A", "descripcion": "moldura caucho tunel RH",
                  "cantidad": 1, "peso_kg": opcional, "tariff_pct": opcional}]
                La descripcion importa: con ella se resuelven arancel y peso.
                peso_kg / tariff_pct SOLO si el usuario los dio.
        cliente: como lo escribió el usuario ("ORGU FORD", "Seguros Zurich").
                 Si no vino, dejalo vacío: se cotiza con tier B y el encabezado
                 lo dice. NUNCA preguntes antes de cotizar.
        vin, brand: identifican la marca/sitio OEM. brand si no hay VIN.
        source: "auto" | "partsouq" | "auvika" (si el mensaje lo pide).
        precio: qué precio cotizar: "auto" (OEM; si no hay, eBay genuino),
                "oem", "ebay" (eBay genuino; para alternos: "alterno").
        margin_pct: solo si el dueño lo forzó (m=XX). -1 = sugerido del tier.
        freight_origin_eur: flete Vilnius->Miami (solo AVK). Si falta, esas
                partes quedan "falta flete EU" y hay que pedirlo.

    Devuelve: ref (para "vendido 1,3"), tabla, filas (detalle por parte),
    sin_cotizar, avisos, cliente_nuevo.
    """
    from shared.cotizacion import nueva_ref, guardar, tabla, fuente_corta, palabra
    sin_cliente = not (cliente or "").strip()
    tier = await _tier_cliente(cliente) if not sin_cliente else await _tier_por_defecto()
    cliente_nuevo = (not sin_cliente) and tier is None
    if not vin and not brand:
        brand = _marca_por_numero([p.get("parte", "") for p in parts])
    m = margin_pct if margin_pct >= 0 else (float(tier["margen_sugerido"]) if tier else None)
    mmin = float(tier["margen_min"]) if tier else None

    q = await quote_parts([{"parte": p.get("parte", ""), "descripcion": p.get("descripcion", "")}
                           for p in parts], vin=vin, brand=brand, source=source,
                          incluir_alterno=(precio in ("ebay", "alterno")))
    if not q.get("ok"):
        return {"ok": False, "error": q.get("error", "fallo la busqueda de precios"), **q}
    por_parte = {r["parte"]: r for r in q["parts"]}

    filas, sin, avisos_peso, avisos_ar, avisos = [], [], [], [], []
    fuentes = set()
    for i, p in enumerate(parts):
        pn = p.get("parte", "")
        desc = p.get("descripcion", "") or ""
        corta = palabra(desc)
        r = por_parte.get(pn, {})
        eb = r.get("ebay") or {}
        oem = r.get("price")
        currency = r.get("currency") or "USD"
        gen = (eb.get("genuine") or {}).get("total_min")
        alt = (eb.get("aftermarket") or {}).get("total_min")

        if precio == "ebay":
            fob, src = gen, "eBay genuino"
        elif precio == "alterno":
            fob, src = alt, "eBay alterno"
        elif precio == "oem":
            fob, src = oem, fuente_corta(r.get("url"), r.get("fuente", "OEM"))
        else:
            if oem:
                fob, src = oem, fuente_corta(r.get("url"), r.get("fuente", "OEM"))
            else:
                fob, src = gen, "eBay genuino"
        if oem and gen and gen < 0.4 * oem:
            avisos.append(f"{corta}: eBay genuino ${gen:,.0f} muy bajo vs OEM, no usar sin revisar")
        if not fob:
            sin.append({"parte": pn, "corta": corta, "motivo": "sin precio"})
            continue
        if currency == "EUR" and not freight_origin_eur:
            sin.append({"parte": pn, "corta": corta, "motivo": "falta flete EU"})
            continue
        fuentes.add(src)

        kw = dict(part_price=float(fob), descripcion=desc, currency=currency,
                  margin_pct=m or 0, freight_origin=freight_origin_eur if currency == "EUR" else 0.0)
        peso = p.get("peso_kg") or r.get("peso_kg")
        if peso:
            kw["weight_kg"] = float(peso)
        if p.get("tariff_pct") is not None:
            kw["tariff_pct"] = float(p["tariff_pct"])
        c = await quote_quito_cost(**kw)
        supuestos = []
        for _ in range(2):   # a lo sumo: resolver arancel y después peso
            if c.get("ok") or not c.get("escalar"):
                break
            if c.get("candidatos"):
                tasas = [cand.get("arancel") for cand in c["candidatos"] if cand.get("arancel") is not None]
                if not tasas:
                    break
                # Iguales: la subpartida no mueve el precio. Distintas: se usa la MÁS ALTA
                # (costo conservador) y se marca para que el dueño la confirme.
                kw["tariff_pct"] = float(max(tasas))
                if len(set(tasas)) > 1:
                    supuestos.append(f"arancel {max(tasas):g}% (máx de {len(set(tasas))})")
                c = await quote_quito_cost(**kw)
                if c.get("ok"):
                    c["revisar_arancel"] = True
            elif "peso" in (c.get("error") or "").lower() and not kw.get("weight_kg"):
                kw["weight_kg"] = _peso_conservador()
                supuestos.append(f"peso {kw['weight_kg']:g} kg supuesto")
                c = await quote_quito_cost(**kw)
            else:
                break
        if supuestos and c.get("ok"):
            avisos.append(f"{corta}: " + ", ".join(supuestos))
        if not c.get("ok"):
            motivo = "falta peso" if "peso" in (c.get("error") or "").lower() else "error"
            sin.append({"parte": pn, "corta": corta, "motivo": motivo, "error": c.get("error")})
            continue
        if c.get("revisar_peso"):
            avisos_peso.append(corta)
        if c.get("revisar_arancel"):
            avisos_ar.append(corta)
        b = c["breakdown"]
        filas.append({
            "n": len(filas) + 1, "parte": pn, "descripcion": desc, "corta": corta,
            "cantidad": p.get("cantidad") or 1, "fuente": src, "url": r.get("url"),
            "currency": currency, "precio_proveedor": float(fob),
            "fob": b["fob_usd"], "costo": c["landed_cost_usd"],
            "precio": c.get("precio_sugerido_usd") if m is not None else None,
            "msrp": r.get("msrp"),
            "peso_kg": c["inputs"]["weight_kg"], "peso_origen": c["peso"].get("origen"),
            "arancel_pct": c["inputs"]["tariff_pct"],
            "subpartida": (c.get("arancel") or {}).get("subpartida"),
            "est": {
                "fob_usd": b["fob_usd"],
                "flete_origen_usd": b["freight_origin_usd"],
                "courier_usd": b["total_siati_usd"],
                "tributos_usd": b["total_aduana_usd"],
                "isd_usd": b["isd_usd"],
                "landed_usd": c["landed_cost_usd"],
            },
            "desglose": c.get("texto"),
        })

    if avisos_peso:
        avisos.insert(0, "verificar peso: " + ("todas" if len(avisos_peso) == len(filas) else ", ".join(avisos_peso)))
    if avisos_ar:
        avisos.insert(1 if avisos_peso else 0, "verificar arancel: " + ", ".join(avisos_ar))
    if cliente_nuevo:
        avisos.insert(0, "cliente nuevo: sin tier, visto bueno del dueño")

    nombre = "SIN CLIENTE" if sin_cliente else (cliente or "?").upper()
    enc = f"{nombre} ({tier['tier'] if tier else '?'}) · {' / '.join(sorted(fuentes)) or '—'}"
    ref = nueva_ref()
    txt = tabla(enc, filas, sin, avisos, pie=f"{ref} · OK / m=XX / precios / no")
    data = {"ref": ref, "creado": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "cliente": cliente, "cliente_tabla": tier["nombre"] if tier else None,
            "tier": tier["tier"] if tier else None, "margen_pct": m, "margen_min": mmin,
            "vin": vin, "brand": brand, "source": source, "precio": precio,
            "filas": filas, "sin_cotizar": sin, "avisos": avisos}
    guardar(ref, data)
    # Respuesta corta a propósito: todo lo que vuelve acá queda en el contexto del
    # bot y se paga en cada mensaje siguiente. El detalle vive en la caché (quote_detail).
    return {"ok": True, "ref": ref, "tabla": txt,
            "nota": "Mandá `tabla` tal cual, en MarkdownV2, como ÚNICO mensaje. Nada más."}


@mcp.tool()
async def quote_detail(ref: str, parte: str = "") -> dict:
    """READ-ONLY. Desglose completo de una parte (o de todas) de una cotización
    hecha con quote_list. Para 'desglose <parte>' / 'detalle'."""
    from shared.cotizacion import cargar
    d = cargar(ref)
    if not d:
        return {"ok": False, "error": f"no existe la cotizacion {ref}"}
    fs = [f for f in d["filas"] if not parte or f["parte"].upper() == parte.upper()
          or str(f["n"]) == parte.strip()]
    return {"ok": True, "ref": d["ref"], "cliente": d["cliente"], "tier": d["tier"],
            "partes": [{"n": f["n"], "parte": f["parte"], "fuente": f["fuente"],
                        "url": f["url"], "desglose": f["desglose"]} for f in fs]}


# ── Cotización vendida → pedido ────────────────────────────────────────────────

@mcp.tool()
async def create_order(ref: str, filas: list[int], usuario: str,
                       nombre_pedido: str = "", notas: str = "", placa: str = "",
                       precios: list[float] | None = None, fecha_entrega: str = "",
                       confirmar: bool = False) -> dict:
    """
    Crear el PEDIDO en workflow-pro a partir de una cotización de quote_list
    ("vendido 1, 3"). Solo Alejandro.

    Args:
        ref:      la referencia de la cotización (ej. C1013-7F3A).
        filas:    números de fila vendidos, de la tabla (# 1, 2, 3...).
        usuario:  "Alejandro".
        nombre_pedido: nombre descriptivo, convención del dashboard:
                  "<MARCA MODELO> <TALLER/DETALLE>" ej. "FORD ESCAPE ORGU GUAYAQUIL".
                  Si falta, preguntá.
        notas:    números del cliente: "PEDIDO 2179 SOLICITUD 567975 PLACA GTK3480".
        placa:    placa del vehículo si se conoce.
        precios:  precio de venta UNITARIO final por fila vendida, en el mismo
                  orden que `filas`, si el dueño pasó sus propios precios.
                  Si no, se usa el sugerido de la cotización.
        fecha_entrega: AAAA-MM-DD prometida; por defecto hoy + 20 días.
        confirmar: False = vista previa; True = escribir, solo tras "si".
    """
    import httpx, uuid as _u, datetime as dt
    from shared.cotizacion import cargar
    from shared.ops import insert, log, usuario_valido, hoy_quito, OpsError
    try:
        u = usuario_valido(usuario)
        if u != "Alejandro":
            raise OpsError("crear pedidos lo hace solo el dueño")
        d = cargar(ref)
        if not d:
            raise OpsError(f"no existe la cotizacion {ref}")
        por_n = {f["n"]: f for f in d["filas"]}
        malas = [n for n in filas if n not in por_n]
        if malas or not filas:
            raise OpsError(f"filas inexistentes en {ref}: {malas or 'ninguna'}")
        if precios and len(precios) != len(filas):
            raise OpsError(f"{len(filas)} filas pero {len(precios)} precios: no cierra")
        if not nombre_pedido.strip():
            raise OpsError("falta nombre_pedido (ej. 'FORD ESCAPE ORGU GUAYAQUIL')")
        hoy = hoy_quito()
        f_ent = fecha_entrega or (dt.date.fromisoformat(hoy) + dt.timedelta(days=20)).isoformat()
        sel = []
        for k, n in enumerate(filas):
            f = por_n[n]
            pv = float(precios[k]) if precios else f.get("precio")
            if pv is None:
                raise OpsError(f"fila {n} sin precio de venta (cliente sin tier): pasá precios")
            sel.append((f, round(pv, 2)))
        avisos = []
        mmin = d.get("margen_min")
        for f, pv in sel:
            if pv < f["costo"]:
                avisos.append(f"{f['corta'] if 'corta' in f else f['parte']}: precio {pv:,.2f} < costo {f['costo']:,.2f}")
            elif mmin is not None and pv < f["costo"] * (1 + mmin / 100):
                avisos.append(f"{f['parte']}: debajo del margen mínimo {mmin:g}%")
        total = sum(pv * (f.get("cantidad") or 1) for f, pv in sel)
        cliente = (d.get("cliente_tabla") or d["cliente"] or "").upper()
        texto = (f"Pedido {nombre_pedido.upper()} — {cliente}\n"
                 + (f"{notas}\n" if notas else "")
                 + f"Entrega prometida {f_ent}\n"
                 + "\n".join(f"  {f['n']}. {f['descripcion'] or f['parte']} ({f['parte']}) "
                             f"x{f.get('cantidad') or 1} · venta {pv:,.2f} · costo est. {f['costo']:,.2f}"
                             for f, pv in sel)
                 + f"\nTotal venta {total:,.2f}"
                 + ("\n⚠ " + "\n⚠ ".join(avisos) if avisos else ""))
        if not confirmar:
            return {"ok": True, "vista_previa": True, "texto": texto + "\n¿Sí?"}

        lote = _u.uuid4().hex
        async with httpx.AsyncClient(timeout=30) as c:
            o = await insert(c, "Order", {
                "numero_pedido": nombre_pedido.upper().strip(), "cliente": cliente,
                "fecha_pedido": hoy, "notas": notas or None, "placa": (placa or "").upper() or None,
                "archivado": False, "created_by": f"bot:{u}"})
            await log(c, u, "create_order", "Order", o["id"], None,
                      {"numero_pedido": o["numero_pedido"], "ref": d["ref"], "_lote": lote})
            for f, pv in sel:
                e = f["est"]
                it = await insert(c, "OrderItem", {
                    "pedido_id": o["id"], "pedido_numero": o["numero_pedido"],
                    "producto_nombre": f["descripcion"] or f["parte"], "numero_parte": f["parte"],
                    "cantidad": f.get("cantidad") or 1, "fecha_entrega_orden": f_ent,
                    "precio_venta": pv, "estado": "adjudicado", "peso_kg": f["peso_kg"],
                    "est_fob_usd": e["fob_usd"], "est_flete_origen_usd": e["flete_origen_usd"],
                    "est_courier_usd": e["courier_usd"], "est_tributos_usd": e["tributos_usd"],
                    "est_isd_usd": e["isd_usd"], "est_landed_usd": e["landed_usd"],
                    "created_by": f"bot:{u}"})
                await log(c, u, "create_order", "OrderItem", it["id"], None,
                          {"parte": f["parte"], "_lote": lote})
        return {"ok": True, "escrito": True, "pedido_id": o["id"],
                "texto": f"✓ Pedido {o['numero_pedido']} creado con {len(sel)} item(s). Ya está en el dashboard."}
    except OpsError as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    mcp.run()
