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


if __name__ == "__main__":
    mcp.run()
