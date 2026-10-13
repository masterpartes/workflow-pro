"""
build_avk_worker.py — arma el bookmarklet del worker AVK.

Toma tools/avk_worker.js, le mete SUPABASE_URL y SUPABASE_ANON_KEY leidos de
.env, y escribe avk_worker_bookmarklet.html en la raiz del repo.

Las credenciales no viajan por el chat ni quedan en git: se leen de .env en la
maquina del dueno al momento de armar el archivo. El HTML resultante SI las
lleva adentro (un bookmarklet no puede leer .env), asi que queda ignorado por
git como cualquier otro secreto local.

Uso:  python tools/build_avk_worker.py
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JS   = REPO / "tools" / "avk_worker.js"
OUT  = REPO / "avk_worker_bookmarklet.html"


def env(nombre: str) -> str:
    for linea in (REPO / ".env").read_text(encoding="utf-8", errors="ignore").splitlines():
        linea = linea.strip()
        if linea.startswith(nombre + "="):
            return linea.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"Falta {nombre} en .env")


def main() -> None:
    js = JS.read_text(encoding="utf-8")
    js = js.replace("__SUPABASE_URL__", env("SUPABASE_URL").rstrip("/"))
    js = js.replace("__SUPABASE_ANON_KEY__", env("SUPABASE_ANON_KEY"))

    # Un bookmarklet es una URL: comentarios fuera y todo en una linea.
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    js = re.sub(r"(^|\s)//[^\n]*", " ", js)
    js = re.sub(r"\s+", " ", js).strip()
    href = "javascript:" + js.replace('"', "&quot;")

    OUT.write_text(
        "<!doctype html><meta charset=utf-8>"
        "<title>AVK worker</title>"
        "<style>body{font:15px/1.6 system-ui;margin:40px;max-width:640px}"
        "a{display:inline-block;background:#1b5e20;color:#fff;padding:10px 18px;"
        "border-radius:8px;text-decoration:none;font-weight:600}"
        "li{margin:6px 0}</style>"
        "<h1>AVK worker</h1>"
        "<p>Arrastra este boton a la barra de marcadores:</p>"
        f'<p><a href="{href}">AVK worker</a></p>'
        "<ol>"
        "<li>Abri <b>avkparts.lt</b> y confirma que estas con la sesion iniciada.</li>"
        "<li>Clic en el marcador. Abajo a la derecha aparece el cartel verde.</li>"
        "<li>Deja esa pestana abierta. Un segundo clic (o clic en el cartel) lo apaga.</li>"
        "</ol>"
        "<p><b>Tenelo a la vista.</b> Chrome frena los temporizadores de las "
        "pestanas de fondo a uno por minuto: si la pestana queda oculta el worker "
        "sigue andando, pero puede tardar hasta un minuto en tomar cada pedido.</p>",
        encoding="utf-8",
    )
    print(f"Escrito: {OUT}")
    print(f"Tamano del bookmarklet: {len(href):,} caracteres")
    if len(href) > 60000:
        print("OJO: algunos navegadores cortan marcadores muy largos.")


if __name__ == "__main__":
    main()
