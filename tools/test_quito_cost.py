"""
test_quito_cost.py — acceptance test for the Quito landed-cost engine.

Run from the repo root on the laptop:

    python tools/test_quito_cost.py          # offline tests only
    python tools/test_quito_cost.py --live   # also tests the live DB + FX path

The offline tests pin FX and pass parameters explicitly, so they prove the ARITHMETIC
without needing Supabase or the network. --live additionally proves the engine reads
cost_params from the database and can fetch a rate.

Reference case (MASTER_PARTES_BUILD_BRIEF_v2.md §3.3):
    Bumper from Lithuania, part EUR 300, origin freight EUR 700, 28.5 kg,
    tariff 15%, FX 1.1592  ->  LANDED $1,505.17
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.quito_cost import (                         # noqa: E402
    calculate_quito_cost,
    CostEngineError,
    format_breakdown,
)

# Values as seeded by supabase/migrations/002_cost_params.sql
PARAMS = {
    "insurance_pct": 1.0,
    "freight_declared_usd_kg": 1.4458,
    "courier_usd_kg": 4.00,
    "nacionalizacion_usd_declaration": 30.00,
    "avg_kg_per_import": 35.0,
    "iva_pct": 15.0,
    "isd_pct": 5.0,
    "fodinfa_pct": 0.5,
    "fx_max_age_hours": 72.0,
}

_fails = []


def check(label, got, want, tol=0.005):
    ok = abs(got - want) <= tol
    print(f"  {'PASS' if ok else 'FAIL'}  {label:<34} {got:>10,.2f}   esperado {want:>10,.2f}")
    if not ok:
        _fails.append(label)


# ── 1. The reference case ──────────────────────────────────────────────────────
print("\n[1] Caso de referencia — parachoques desde Lituania (brief §3.3)")
r = calculate_quito_cost(
    part_price=300.0,
    weight_kg=28.5,
    tariff_pct=15.0,
    currency="EUR",
    freight_origin=700.0,
    freight_origin_currency="EUR",
    params=PARAMS,
    fx_eur_usd=1.1592,
)
b = r["breakdown"]
check("FOB", b["fob_usd"], 347.76)
check("Flete declarado", b["freight_declared_usd"], 41.21)
check("CIF", b["cif_usd"], 392.44)
check("Total aduana", b["total_aduana_usd"], 128.82)
check("ISD", b["isd_usd"], 57.96)
check("SIATI", b["total_siati_usd"], 159.19)
check("PRECIO_UIO", b["precio_uio_usd"], 693.73)
check("Flete origen", b["freight_origin_usd"], 811.44)
check("LANDED  <-- criterio de aceptacion", r["landed_cost_usd"], 1505.17)

print()
print(format_breakdown(r))

# ── 2. Tier pricing ────────────────────────────────────────────────────────────
print("\n[2] Precio por tier — margen aplicado al landed, sin deducir credito IVA")
for tier, margin, expected in [("B sugerido", 35.0, 2031.98), ("C sugerido", 50.0, 2257.76)]:
    rr = calculate_quito_cost(
        part_price=300.0, weight_kg=28.5, tariff_pct=15.0, currency="EUR",
        freight_origin=700.0, margin_pct=margin, params=PARAMS, fx_eur_usd=1.1592,
    )
    check(f"precio {tier} ({margin:.0f}%)", rr["precio_sugerido_usd"], expected)

# ── 3. US part: no FX, no origin freight ───────────────────────────────────────
print("\n[3] Parte de EEUU — USD, sin flete de origen, sin FX")
us = calculate_quito_cost(
    part_price=100.0, weight_kg=2.0, tariff_pct=15.0, currency="USD", params=PARAMS,
)
ub = us["breakdown"]
check("FOB = precio", ub["fob_usd"], 100.00)
check("Flete origen = 0", ub["freight_origin_usd"], 0.00)
check("ISD solo sobre FOB", ub["isd_usd"], 5.00)
check("CIF", ub["cif_usd"], 103.89)

# ── 4. The engine must REFUSE rather than guess ────────────────────────────────
print("\n[4] El motor debe negarse, no adivinar")
for label, kwargs in [
    ("tariff_pct=None escala",   dict(part_price=100.0, weight_kg=1.0, tariff_pct=None)),
    ("peso 0 rechazado",         dict(part_price=100.0, weight_kg=0,   tariff_pct=15.0)),
    ("precio negativo rechazado",dict(part_price=-1.0,  weight_kg=1.0, tariff_pct=15.0)),
]:
    try:
        calculate_quito_cost(params=PARAMS, **kwargs)
        print(f"  FAIL  {label:<34} no lanzo excepcion")
        _fails.append(label)
    except CostEngineError:
        print(f"  PASS  {label}")

# ── 5. Live path ───────────────────────────────────────────────────────────────
if "--live" in sys.argv:
    print("\n[5] Ruta en vivo — cost_params desde Supabase + FX del BCE")
    from shared.quito_cost import load_params, get_fx_eur_usd
    try:
        p = load_params()
        print(f"  PASS  cost_params cargado: {len(p)} claves")
        for k, v in sorted(p.items()):
            flag = "" if abs(v - PARAMS.get(k, v)) < 1e-9 else "   <-- DIFIERE del test"
            print(f"          {k:<34} {v}{flag}")
        fx = get_fx_eur_usd()
        print(f"  PASS  FX EUR/USD = {fx['rate']} ({fx['date']})")
        live = calculate_quito_cost(
            part_price=300.0, weight_kg=28.5, tariff_pct=15.0, currency="EUR",
            freight_origin=700.0, margin_pct=35.0,
        )
        print(f"  INFO  landed con parametros y FX reales: "
              f"${live['landed_cost_usd']:,.2f}  "
              f"(referencia ${1505.17:,.2f} con FX 1.1592)")
    except CostEngineError as e:
        print(f"  FAIL  ruta en vivo: {e}")
        _fails.append("live")
else:
    print("\n[5] Ruta en vivo omitida — use --live para probar Supabase + FX")

# ── Verdict ────────────────────────────────────────────────────────────────────
print()
if _fails:
    print(f"FALLARON {len(_fails)} comprobaciones: {_fails}")
    sys.exit(1)
print("TODAS LAS COMPROBACIONES PASARON")
