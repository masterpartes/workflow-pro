"""
build_userscript.py — arma UN solo userscript (Tampermonkey) con los workers de
cola: AVK (precios) y PartSouq (catalogo por VIN). Elige el worker segun el
dominio de la pestana y arranca solo, sin marcador ni clic.

Toma tools/avk_worker.js y tools/catalog_worker.js (la fuente de verdad, no se
duplican), les mete SUPABASE_URL/ANON_KEY de .env y escribe
masterpartes_worker.user.js en la raiz. Lleva credenciales: va en .gitignore.

Uso:  python tools/build_userscript.py
Partslink24: incluido el 28-nov-2026 por decision del dueno (su cuenta, su pestana con sesion).
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "masterpartes_worker.user.js"
WORKERS = [
    ("avk", "tools/avk_worker.js", r"avkparts"),
    ("catalog", "tools/catalog_worker.js", r"partsouq"),
    ("pl24", "tools/pl24_worker.js", r"partslink24"),
]


def env(nombre):
    for linea in (REPO / ".env").read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.strip()
        if linea.startswith(nombre + "="):
            return linea.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"Falta {nombre} en .env")


def main():
    url, key = env("SUPABASE_URL").rstrip("/"), env("SUPABASE_ANON_KEY")
    partes = []
    for nombre, ruta, host in WORKERS:
        js = (REPO / ruta).read_text(encoding="utf-8")
        js = js.replace("__SUPABASE_URL__", url).replace("__SUPABASE_ANON_KEY__", key)
        # En el userscript no hay clic de usuario: nunca mostrar alert() de
        # "pestana equivocada" (el router ya eligio el worker por dominio).
        js = re.sub(r"\balert\([^;]*\);", "", js)
        partes.append(
            f"  if (/{host}/.test(location.hostname) && esWorker) {{\n"
            f"    try {{\n{js}\n    }} catch (e) {{ console.error('[masterpartes {nombre}]', e); }}\n"
            f"  }}\n"
        )
    cab = (
        "// ==UserScript==\n"
        "// @name         Master Partes workers (AVK + PartSouq + Partslink24)\n"
        "// @namespace    masterpartes\n"
        "// @version      5\n"
        "// @description  Un solo worker: elige AVK o PartSouq segun la pagina y arranca solo.\n"
        "// @match        https://avkparts.lt/*\n"
        "// @match        https://www.avkparts.lt/*\n"
        "// @match        https://partsouq.com/*\n"
        "// @match        https://www.partsouq.com/*\n"
        "// @match        https://www.partslink24.com/*\n"
        "// @run-at       document-idle\n"
        "// @noframes\n"
        "// @grant        none\n"
        "// ==/UserScript==\n"
    )
    cuerpo = (
        "(function () {\n  'use strict';\n"
        "  if (window.__mpUserscript) return;   // una sola vez por pestana\n"
        "  window.__mpUserscript = true;\n"
        "  // Solo la pestana de trabajo (MODO_REMOTO la abre con #mpworker). Las pestanas que abre\n"
        "  // el agente o el dueno en el mismo sitio NO arrancan otro worker.\n"
        "  if (location.hash.indexOf('mpworker') >= 0) sessionStorage.setItem('mpworker', '1');\n"
        "  var esWorker = sessionStorage.getItem('mpworker') === '1';\n"
        + "".join(partes) + "})();\n"
    )
    OUT.write_text(cab + cuerpo, encoding="utf-8")
    print(f"Escrito: {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
