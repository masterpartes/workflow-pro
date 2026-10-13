"""
cotizacion.py — armado de la tabla interna y caché local de cotizaciones.

La tabla sigue las reglas de C:\\MasterPartesBot\\CLAUDE.md:
  * todo dentro de un bloque ``` (el bot la manda en MarkdownV2)
  * ninguna línea pasa de 42 caracteres
  * sin centavos, sin margen en el encabezado, sin total
  * avisos agrupados al final

Cada cotización se guarda en workflow-pro/data/cotizaciones/<ref>.json para que
create_order tome los números EXACTOS (no los que el modelo recuerde).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import secrets
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

_DIR = Path(__file__).resolve().parents[2] / "data" / "cotizaciones"
QUITO = _dt.timezone(_dt.timedelta(hours=-5))


def nueva_ref() -> str:
    # corta y fácil de dictar: C1013-7F3A
    return f"C{_dt.datetime.now(QUITO):%m%d}-{secrets.token_hex(2).upper()}"


def guardar(ref: str, data: dict) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    (_DIR / f"{ref}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                      encoding="utf-8")


def cargar(ref: str) -> Optional[dict]:
    ref = (ref or "").strip().upper()
    if not re.fullmatch(r"C\d{4}-[0-9A-F]{4}", ref):
        return None
    p = _DIR / f"{ref}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fuente_corta(url: Optional[str], fallback: str = "") -> str:
    if not url:
        return fallback
    host = urlparse(url).netloc.lower().replace("www.", "")
    return host.split(".")[0] if host else fallback


def palabra(desc: str, n: int = 7) -> str:
    """Primera palabra significativa, en minúscula, cortada a n."""
    stop = {"de", "del", "la", "el", "los", "las", "para", "con", "y"}
    for w in re.split(r"[\s/,.-]+", (desc or "").lower()):
        if w and w not in stop:
            return w[:n]
    return "?"


def _n(x) -> str:
    return "" if x is None else f"{x:,.0f}".replace(",", "")


def tabla(encabezado: str, filas: list[dict], sin_cotizar: list[dict],
          avisos: list[str], pie: str = "OK / m=XX / precios / no") -> str:
    """Filas: {n, parte, corta, fob, costo, precio}. Ancho máx 42."""
    out = [encabezado[:42]]
    if filas:
        out.append(f"{'#':<2} {'PARTE':<13} {'DESCRIP':<7}{'FOB':>5}{'COSTO':>6}{'PRECIO':>7}")
    for f in filas:
        out.append(f"{f['n']:<2} {f['parte'][:13]:<13} {f['corta'][:7]:<7}"
                   f"{_n(f['fob']):>5}{_n(f['costo']):>6}{_n(f.get('precio')) or '—':>7}")
    if sin_cotizar:
        out += ([""] if filas else []) + [f"Sin cotizar ({len(sin_cotizar)})"]
        for s in sin_cotizar:
            out.append(f"{s['parte'][:13]:<13}  {s['corta'][:9]:<9} {s['motivo']}"[:42])
    if avisos:
        out.append("")
        for a in avisos:
            # cortar avisos largos en líneas de 42
            linea = "⚠ " + a
            while len(linea) > 42:
                cut = linea.rfind(" ", 0, 42)
                cut = cut if cut > 10 else 42
                out.append(linea[:cut])
                linea = "  " + linea[cut:].lstrip()
            out.append(linea)
    out.append(pie)
    return "```\n" + "\n".join(out) + "\n```"
