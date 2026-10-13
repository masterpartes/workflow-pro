"""
quito_cost.py — Quito landed-cost engine.

Ports the cost chain from cotizacion_bulk.xlsm, corrected and validated against a
real customs declaration and the forwarder's invoice.
Specification: MASTER_PARTES_BUILD_BRIEF_v2.md §3.

Two independent chains:

  * Ecuadorian customs sees FOB + insurance + DECLARED freight (Miami->Quito).
  * The origin leg (e.g. Vilnius->Miami) is paid separately, never enters the
    customs valuation, but IS part of landed cost and margin is taken on it.

Design rules, do not weaken them:

  * Every constant comes from the `cost_params` table. No literals in this file.
  * FX is looked up live and is never guessed. If the rate cannot be fetched or
    is stale, the function RAISES rather than returning a plausible number.
  * The function returns the whole breakdown, not just a total. The breakdown is
    shown to a human before approval; it is not optional.
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

import httpx

from shared.config import SUPABASE_URL, SUPABASE_ANON_KEY

# ── Errors ─────────────────────────────────────────────────────────────────────


class CostEngineError(RuntimeError):
    """Raised when the engine cannot produce a trustworthy number."""


# ── Parameters ─────────────────────────────────────────────────────────────────

_PARAM_CACHE: Optional[dict] = None

_REQUIRED = (
    "insurance_pct",
    "freight_declared_usd_kg",
    "courier_usd_kg",
    "nacionalizacion_usd_declaration",
    "avg_kg_per_import",
    "iva_pct",
    "isd_pct",
    "fodinfa_pct",
)


def load_params(force: bool = False) -> dict:
    """Pull cost_params from Supabase. Cached for the life of the process."""
    global _PARAM_CACHE
    if _PARAM_CACHE is not None and not force:
        return _PARAM_CACHE

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise CostEngineError(
            "SUPABASE_URL / SUPABASE_ANON_KEY not set — cannot load cost_params. "
            "Refusing to quote on hardcoded defaults."
        )

    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Accept": "application/json",
    }
    try:
        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/cost_params",
            params={"select": "key,value", "limit": "200"},
            headers=headers,
            timeout=10,
        )
    except Exception as e:                                    # noqa: BLE001
        raise CostEngineError(f"cost_params unreachable: {e}") from e

    if resp.status_code != 200:
        raise CostEngineError(
            f"cost_params query failed {resp.status_code}: {resp.text[:200]}"
        )

    params = {r["key"]: float(r["value"]) for r in resp.json()}

    missing = [k for k in _REQUIRED if k not in params]
    if missing:
        raise CostEngineError(
            f"cost_params is missing required keys: {missing}. "
            "Apply supabase/migrations/002_cost_params.sql."
        )

    _PARAM_CACHE = params
    return params


# ── FX ─────────────────────────────────────────────────────────────────────────

_FX_CACHE: Optional[tuple] = None       # (rate, quote_date, fetched_at)

_FX_URL = "https://api.frankfurter.dev/v1/latest"


def get_fx_eur_usd(max_age_hours: float = 72.0, force: bool = False) -> dict:
    """
    Live EUR->USD from the ECB reference series. No buffer is applied: FX risk is
    carried in the margin, per brief §3.2.

    Raises rather than falling back to a stale or invented rate.
    """
    global _FX_CACHE
    now = _dt.datetime.now(_dt.timezone.utc)

    if _FX_CACHE and not force:
        rate, qdate, fetched = _FX_CACHE
        if (now - fetched).total_seconds() < 3600:
            return {"rate": rate, "date": qdate, "cached": True}

    try:
        resp = httpx.get(_FX_URL, params={"from": "EUR", "to": "USD"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rate = float(data["rates"]["USD"])
        qdate = data["date"]
    except Exception as e:                                    # noqa: BLE001
        raise CostEngineError(
            f"Could not fetch EUR/USD: {e}. Refusing to quote on a guessed rate."
        ) from e

    age_h = (now.date() - _dt.date.fromisoformat(qdate)).days * 24
    if age_h > max_age_hours:
        raise CostEngineError(
            f"EUR/USD quote is {age_h}h old (dated {qdate}), limit {max_age_hours}h. "
            "Refusing to quote."
        )

    _FX_CACHE = (rate, qdate, now)
    return {"rate": rate, "date": qdate, "cached": False}


# ── The engine ─────────────────────────────────────────────────────────────────


def calculate_quito_cost(
    part_price: float,
    weight_kg: float,
    tariff_pct: float,
    *,
    currency: str = "USD",
    freight_origin: float = 0.0,
    freight_origin_currency: str = "EUR",
    margin_pct: Optional[float] = None,
    params: Optional[dict] = None,
    fx_eur_usd: Optional[float] = None,
) -> dict:
    """
    Landed cost in Quito, with the full breakdown.

    Args:
        part_price:   Supplier price of the part, in `currency`.
        weight_kg:    Actual weight. Miami->Quito bills actual weight, not
                      volumetric — the Saturday consolidated flight is exempt.
        tariff_pct:   Ad-valorem rate for the subpartida, e.g. 15 for 15%.
                      Resolve via shared.tariff_lookup; never default it to 0.
        currency:     "USD" (US OEM sites, eBay) or "EUR" (AVK).
        freight_origin: Origin-leg freight, e.g. Vilnius->Miami. 0 for US parts.
                      Outside the customs valuation, inside landed cost.
        margin_pct:   Optional tier margin, e.g. 35 for 35%. If given, the result
                      includes precio_sugerido = landed * (1 + margin).
        params:       Override cost_params (tests). Defaults to the DB.
        fx_eur_usd:   Override FX (tests). Defaults to the live ECB rate.

    Returns:
        dict with every intermediate line plus `landed_cost_usd`.

    Raises:
        CostEngineError if params or FX are unavailable, or inputs are unusable.
    """
    if weight_kg is None or weight_kg <= 0:
        raise CostEngineError(f"weight_kg must be positive, got {weight_kg!r}")
    if part_price is None or part_price < 0:
        raise CostEngineError(f"part_price must be non-negative, got {part_price!r}")
    if tariff_pct is None:
        raise CostEngineError(
            "tariff_pct is required. A missing tariff must escalate to a human, "
            "never silently default to 0%."
        )

    p = params if params is not None else load_params()

    needs_fx = (currency.upper() == "EUR") or (
        freight_origin and freight_origin_currency.upper() == "EUR"
    )
    fx_meta = None
    if fx_eur_usd is None:
        if needs_fx:
            fx_meta = get_fx_eur_usd(p.get("fx_max_age_hours", 72.0))
            fx = fx_meta["rate"]
        else:
            fx = 1.0
    else:
        fx = float(fx_eur_usd)

    iva = p["iva_pct"] / 100.0

    # ── Goods, converted to USD ────────────────────────────────────────────────
    fob = part_price * (fx if currency.upper() == "EUR" else 1.0)
    freight_origin_usd = freight_origin * (
        fx if freight_origin_currency.upper() == "EUR" else 1.0
    )

    # ── Customs valuation: origin leg deliberately excluded ────────────────────
    insurance = fob * p["insurance_pct"] / 100.0
    freight_declared = p["freight_declared_usd_kg"] * weight_kg
    cif = fob + insurance + freight_declared

    advalorem = cif * tariff_pct / 100.0
    fodinfa = cif * p["fodinfa_pct"] / 100.0
    iva_aduana = iva * (cif + advalorem + fodinfa)
    total_aduana = advalorem + fodinfa + iva_aduana

    # ── ISD: everything paid abroad. Miami->Quito is billed locally. ───────────
    isd = (fob + freight_origin_usd) * p["isd_pct"] / 100.0

    # ── Courier bill (SIATI). $4/kg all-in + $30 per declaration, prorated. ────
    courier = p["courier_usd_kg"] * weight_kg
    nacionalizacion = (
        p["nacionalizacion_usd_declaration"] * weight_kg / p["avg_kg_per_import"]
    )
    total_siati = (courier + nacionalizacion) * (1 + iva)

    precio_uio = fob + isd + total_aduana + total_siati
    landed = precio_uio + freight_origin_usd

    r2 = lambda x: round(x, 2)                                # noqa: E731
    out = {
        "inputs": {
            "part_price": part_price,
            "currency": currency.upper(),
            "weight_kg": weight_kg,
            "tariff_pct": tariff_pct,
            "freight_origin": freight_origin,
            "freight_origin_currency": freight_origin_currency.upper(),
        },
        "fx": {"eur_usd": fx, **(fx_meta or {})},
        "breakdown": {
            "fob_usd":            r2(fob),
            "insurance_usd":      r2(insurance),
            "freight_declared_usd": r2(freight_declared),
            "cif_usd":            r2(cif),
            "advalorem_usd":      r2(advalorem),
            "fodinfa_usd":        r2(fodinfa),
            "iva_aduana_usd":     r2(iva_aduana),
            "total_aduana_usd":   r2(total_aduana),
            "isd_usd":            r2(isd),
            "courier_usd":        r2(courier),
            "nacionalizacion_usd": r2(nacionalizacion),
            "total_siati_usd":    r2(total_siati),
            "precio_uio_usd":     r2(precio_uio),
            "freight_origin_usd": r2(freight_origin_usd),
        },
        "landed_cost_usd": r2(landed),
        # Recoverable against output IVA. NOT deducted from the customer's price.
        "credito_iva_usd": r2(iva_aduana),
        "params_used": {k: p[k] for k in _REQUIRED if k in p},
    }

    if margin_pct is not None:
        precio = landed * (1 + margin_pct / 100.0)
        out["margin_pct"] = margin_pct
        out["precio_sugerido_usd"] = r2(precio)
        out["ganancia_usd"] = r2(precio - landed)

    return out


def format_breakdown(result: dict) -> str:
    """Human-readable breakdown, Spanish — this is what the bot shows before approval."""
    b = result["breakdown"]
    lines = [
        f"FOB parte                  $ {b['fob_usd']:>9,.2f}",
        f"Seguro                     $ {b['insurance_usd']:>9,.2f}",
        f"Flete declarado            $ {b['freight_declared_usd']:>9,.2f}",
        f"CIF (base aduanera)        $ {b['cif_usd']:>9,.2f}",
        f"  Advalorem                $ {b['advalorem_usd']:>9,.2f}",
        f"  FODINFA                  $ {b['fodinfa_usd']:>9,.2f}",
        f"  IVA aduana               $ {b['iva_aduana_usd']:>9,.2f}",
        f"  Total aduana             $ {b['total_aduana_usd']:>9,.2f}",
        f"ISD                        $ {b['isd_usd']:>9,.2f}",
        f"Courier + nacionalizacion  $ {b['total_siati_usd']:>9,.2f}",
        f"PRECIO_UIO                 $ {b['precio_uio_usd']:>9,.2f}",
    ]
    if b["freight_origin_usd"]:
        lines.append(f"Flete origen               $ {b['freight_origin_usd']:>9,.2f}")
    lines.append(f"COSTO LANDED               $ {result['landed_cost_usd']:>9,.2f}")
    if "precio_sugerido_usd" in result:
        lines.append(
            f"Precio sugerido ({result['margin_pct']:.0f}%)    "
            f"$ {result['precio_sugerido_usd']:>9,.2f}"
        )
    return "\n".join(lines)
