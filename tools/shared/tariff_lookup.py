"""
Tariff lookup: given a part description, return the best matching
SUBPARTIDA and ARANCEL from the Supabase TariffCode table.

Strategy:
1. Pull all tariff codes from Supabase (small table, cache in memory).
2. Normalize description → keyword match against descripcion_referencial.
3. If ambiguous or no match → use Claude to pick from top 5 candidates.

Endurecido 20-sep-2026 (ver MASTER_PARTES_BUILD_BRIEF_v2.md §7, Stage 2):

  * Un `arancel` nulo YA NO se convierte en 0%. Antes, `float(x or 0)` borraba
    el arancel de la cotización sin que nada lo avisara.
  * Una coincidencia ambigua ya no se resuelve en silencio tomando el primer
    candidato: `lookup_detailed()` devuelve la confianza y los candidatos
    considerados para que el bot escale en vez de inventar.

`lookup()` conserva su forma original a propósito: `enrich_excel.py` e
`import_manual.py` dependen de ella. Lo nuevo vive en `lookup_detailed()`.
"""
import re
import json
import time
import httpx
from typing import Optional
from shared.config import SUPABASE_URL, SUPABASE_ANON_KEY, ANTHROPIC_API_KEY

_TARIFF_CACHE: list[dict] | None = None
_TARIFF_CACHE_AT: float = 0.0
_TARIFF_TTL_S = 600      # 10 min: una correccion en TariffCode entra sola,
                         # sin reiniciar el servidor MCP.


class TariffLookupError(RuntimeError):
    """Raised when the tariff table itself cannot be trusted or reached."""


def _fetch_tariff_codes() -> list[dict]:
    """Pull all TariffCode rows from Supabase."""
    global _TARIFF_CACHE, _TARIFF_CACHE_AT
    if _TARIFF_CACHE is not None and (time.time() - _TARIFF_CACHE_AT) < _TARIFF_TTL_S:
        return _TARIFF_CACHE

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("[tariff] SUPABASE_URL / SUPABASE_ANON_KEY not set — skipping lookup")
        return []

    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Accept": "application/json",
    }
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/TariffCode",
        params={"select": "subpartida,arancel,descripcion_referencial", "limit": "2000"},
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 200:
        _TARIFF_CACHE = resp.json()
        _TARIFF_CACHE_AT = time.time()
        print(f"[tariff] Loaded {len(_TARIFF_CACHE)} tariff codes from Supabase")
    else:
        print(f"[tariff] Supabase error {resp.status_code}: {resp.text[:200]}")
        _TARIFF_CACHE = []

    return _TARIFF_CACHE


def _normalize(text: str) -> str:
    text = text.upper()
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return " ".join(text.split())


def _head(text: str) -> str:
    """Primer sustantivo significativo. En espanol el nucleo va primero."""
    toks = [t for t in _normalize(text).split() if len(t) >= 3]
    return toks[0] if toks else ""


def _covered_heads(tariff_desc: str) -> list:
    """
    Los nucleos que una partida cubre.

    Una descripcion de TariffCode es una LISTA de piezas, no una frase:
    "PARACHOQUES / VINCHA" cubre dos cosas distintas. Se parte por / y , y se
    toma el nucleo de cada tramo.

    Esto conserva la distincion que importa: "TORNILLO PARACHOQUES" es UN tramo
    cuyo nucleo es TORNILLO, asi que un parachoques NO cobra bono ahi. Pero
    "MOLDURA / GUARDAFANGO" cubre las dos, y cada una cobra su bono.
    """
    out = []
    for chunk in re.split(r"[/,;]", tariff_desc or ""):
        h = _head(chunk)
        if h:
            out.append(h)
    return out


def _keyword_score(description: str, tariff_desc: str) -> int:
    """
    Puntaje de coincidencia, con BONO DE NUCLEO.

    Las descripciones de TariffCode son cortas ("PARACHOQUES / VINCHA"), asi que
    contar palabras sueltas casi nunca pasa de 2 y no distingue "es un
    parachoques" de "es un tornillo PARA parachoques". El bono resuelve eso:
    si la partida ARRANCA con el mismo sustantivo que la parte, es la partida
    de esa cosa, no de un accesorio suyo.
    """
    words = set(_normalize(description).split())
    target = _normalize(tariff_desc or "")
    score = sum(1 for w in words if w in target and len(w) >= 3)
    if not score:
        return 0
    h_part = _head(description)
    if h_part:
        for h_tar in _covered_heads(tariff_desc):
            if h_part == h_tar or (len(h_part) >= 5 and len(h_tar) >= 5
                                   and (h_part.startswith(h_tar) or h_tar.startswith(h_part))):
                score += 3    # "PARACHOQUES DEL." vs "PARACHOQUES / VINCHA"
                break
    return score


def _claude_pick(description: str, candidates: list[dict]) -> Optional[dict]:
    """Use Claude API to pick the best tariff from candidates."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        candidates_text = "\n".join(
            f"{i+1}. {c['subpartida']} | {c['arancel']}% | {c['descripcion_referencial']}"
            for i, c in enumerate(candidates)
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": (
                    f"Parte: {description}\n"
                    f"Candidatos arancelarios:\n{candidates_text}\n\n"
                    "Responde SOLO con el número del candidato más apropiado (1, 2, 3, etc.) "
                    "o 0 si ninguno aplica."
                )
            }]
        )
        choice = int(re.search(r"\d+", msg.content[0].text).group(0))
        if 1 <= choice <= len(candidates):
            return candidates[choice - 1]
    except Exception as e:
        print(f"[tariff] Claude pick error: {e}")
    return None


def lookup_detailed(description: str) -> dict:
    """
    Devuelve:
      {
        "ok": bool,
        "subpartida": str | None,
        "arancel_pct": float | None,
        "confianza": "alta" | "media" | "baja" | "ninguna",
        "metodo": "keyword" | "claude" | "ninguno",
        "candidatos": [{"subpartida","arancel","descripcion_referencial","score"}],
        "escalar": bool,
        "nota": str,
      }

    `escalar: True` significa "preguntale al dueño", NUNCA "usá 0%".
    """
    codes = _fetch_tariff_codes()
    if not codes:
        raise TariffLookupError(
            "TariffCode no devolvió filas. Si la tabla tiene datos, al rol anon "
            "le falta una policy de SELECT (ver §2 del brief)."
        )

    scored = sorted(
        ((c, _keyword_score(description, c.get("descripcion_referencial", "")))
         for c in codes),
        key=lambda x: -x[1],
    )
    top = [dict(c, score=s) for c, s in scored if s > 0][:5]

    base = {"subpartida": None, "arancel_pct": None, "candidatos": top,
            "escalar": True, "ok": False}

    if not top:
        return {**base, "confianza": "ninguna", "metodo": "ninguno",
                "nota": f"Ninguna partida coincide con '{description}'."}

    best, metodo, confianza = None, "keyword", "baja"
    s0 = top[0]["score"]
    s1 = top[1]["score"] if len(top) > 1 else 0

    # Confianza por MARGEN, no por puntaje absoluto: las descripciones cortas
    # nunca acumulan puntaje alto por si solas.
    if s0 - s1 >= 3:
        best, confianza = top[0], "alta"
    elif s0 > s1:
        best, confianza = top[0], "media"
    elif len(top) == 1:
        best, confianza = top[0], "media"
    else:
        picked = _claude_pick(description, top)
        if picked:
            best, metodo, confianza = dict(picked), "claude", "media"
        else:
            # Antes: se tomaba top[0] en silencio. Ahora se escala.
            return {**base, "confianza": "baja", "metodo": "keyword",
                    "nota": (f"Coincidencia ambigua para '{description}': "
                             f"{len(top)} candidatos con puntajes parecidos "
                             f"({s0} vs {s1}). No se elige por adivinanza.")}

    arancel = best.get("arancel")
    if arancel is None:
        # NUNCA 0. Un arancel nulo es un dato faltante, no una tasa cero.
        return {**base, "confianza": "ninguna", "metodo": metodo,
                "subpartida": best["subpartida"],
                "nota": (f"La partida {best['subpartida']} existe pero tiene el "
                         "arancel vacío en TariffCode. Hay que completarlo; no se "
                         "asume 0%.")}

    return {"ok": True, "subpartida": best["subpartida"],
            "arancel_pct": float(arancel), "confianza": confianza,
            "metodo": metodo, "candidatos": top, "escalar": confianza == "baja",
            "nota": best.get("descripcion_referencial", "")}


def lookup(description: str) -> dict:
    """
    Forma original, preservada para enrich_excel.py / import_manual.py.
    Returns {"subpartida": str, "arancel": float} or {None, None}.
    """
    try:
        d = lookup_detailed(description)
    except TariffLookupError:
        return {"subpartida": None, "arancel": None}
    if not d["ok"]:
        return {"subpartida": d.get("subpartida"), "arancel": None}
    return {"subpartida": d["subpartida"], "arancel": d["arancel_pct"]}


def lookup_batch(descriptions: list[str]) -> list[dict]:
    """Bulk lookup — one result per description."""
    _fetch_tariff_codes()  # loads once
    return [lookup(d) for d in descriptions]
