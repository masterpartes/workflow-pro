"""
part_weight.py — estimate a part's REAL weight from its description.

Used for the Miami -> Quito leg, which is billed on real weight (the consolidated
Saturday flight carries a volumetric exemption). NOT for the origin -> Miami leg,
where volumetric size drives the cost.

Seeded from 1,548 real despatch lines. See supabase/migrations/004_part_weight.sql.

Two rules this module exists to enforce:

  1. Match the HEAD NOUN only. Spanish part names put the head first:
     "CERRADURA de puerta" is a lock, not a door. Matching the modifier gave a
     0.5 kg latch the 30 kg of a door — a 50x error, found in testing.

  2. Never return a bare number. Every estimate carries n, dispersion and a
     confidence level, because the human approving the quote has to be able to
     judge it and correct it before the price goes out.
"""
from __future__ import annotations

import re
from typing import Optional

import httpx

from shared.config import SUPABASE_URL, SUPABASE_ANON_KEY


class WeightLookupError(RuntimeError):
    pass


_CACHE: Optional[dict] = None
_MIN_PREFIX = 5          # 'PLAT' (4) must not prefix-match 'PLATINA'


def _fetch(table: str, select: str) -> list:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise WeightLookupError("SUPABASE_URL / SUPABASE_ANON_KEY not set")
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Accept": "application/json",
    }
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/{table}",
                  params={"select": select, "limit": "2000"},
                  headers=headers, timeout=10)
    if r.status_code != 200:
        raise WeightLookupError(f"{table} query failed {r.status_code}: {r.text[:160]}")
    return r.json()


def load(force: bool = False) -> dict:
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE
    rows = _fetch("part_weight", "clave,palabras,peso_kg,n_muestras,dispersion,confianza")
    if not rows:
        # An empty result from PostgREST usually means RLS with no read policy,
        # not an empty table. Say so rather than silently estimating nothing.
        raise WeightLookupError(
            "part_weight returned no rows. If the table has data, the anon role is "
            "missing a SELECT policy — see migration 004."
        )
    alias = {a["abreviatura"]: a["canonico"] for a in _fetch("part_alias", "abreviatura,canonico")}
    k1, k2 = {}, {}
    for r in rows:
        entry = (float(r["peso_kg"]), int(r["n_muestras"]),
                 float(r["dispersion"]), r["confianza"])
        (k2 if int(r["palabras"]) == 2 else k1)[r["clave"]] = entry
    _CACHE = {"k1": k1, "k2": k2, "alias": alias}
    return _CACHE


def _tokens(desc: str, alias: dict) -> list:
    s = str(desc).upper()
    for a, b in (("Á","A"),("É","E"),("Í","I"),("Ó","O"),("Ú","U"),("Ñ","N")):
        s = s.replace(a, b)
    toks = [t for t in re.split(r"[^A-Z0-9]+", s) if len(t) > 2]
    return [alias.get(t, t) for t in toks]


def _prefix(a: str, b: str) -> bool:
    return (len(a) >= _MIN_PREFIX and len(b) >= _MIN_PREFIX
            and (a.startswith(b) or b.startswith(a)))


def estimate_weight(description: str, tables: Optional[dict] = None) -> Optional[dict]:
    """
    Returns {'peso_kg', 'clave', 'n_muestras', 'dispersion', 'confianza'} or None.

    None means "no basis for an estimate" and MUST be escalated to a human —
    it does not mean zero, and it must never be turned into a default.
    """
    t = tables if tables is not None else load()
    toks = _tokens(description, t["alias"])
    if not toks:
        return None
    head = toks[0]

    if len(toks) > 1:
        for clave, (kg, n, disp, conf) in t["k2"].items():
            a, b = clave.split(" ", 1)
            if (head == a or _prefix(head, a)) and (toks[1] == b or _prefix(toks[1], b)):
                return dict(peso_kg=kg, clave=clave, n_muestras=n,
                            dispersion=disp, confianza=conf, match="2 palabras")

    if head in t["k1"]:
        kg, n, disp, conf = t["k1"][head]
        return dict(peso_kg=kg, clave=head, n_muestras=n,
                    dispersion=disp, confianza=conf, match="exacta")

    for clave, (kg, n, disp, conf) in t["k1"].items():
        if _prefix(head, clave):
            return dict(peso_kg=kg, clave=clave, n_muestras=n,
                        dispersion=disp, confianza=conf, match="prefijo")
    return None


def describe(est: Optional[dict]) -> str:
    """One line for the human who has to approve or correct the weight."""
    if not est:
        return "Peso: SIN ESTIMACION — indicar el peso real para poder cotizar."
    warn = {"alta": "", "media": "  (verificar)", "baja": "  (BAJA CONFIANZA — verificar)"}
    return (f"Peso: {est['peso_kg']:.2f} kg estimado de '{est['clave']}' "
            f"(n={est['n_muestras']}, dispersion {est['dispersion']:.1f}x, "
            f"confianza {est['confianza']}){warn[est['confianza']]}")
