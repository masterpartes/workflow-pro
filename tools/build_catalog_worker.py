"""
build_catalog_worker.py — arma el bookmarklet del worker de catalogo (PartSouq).

Igual que build_avk_worker.py: toma tools/catalog_worker.js, le mete SUPABASE_URL
y SUPABASE_ANON_KEY leidos de .env y escribe catalog_worker_bookmarklet.html en la
raiz del repo. Ese HTML lleva las credenciales adentro: queda ignorado por git
(ver .gitignore) y no se comparte.

Uso:  python tools/build_catalog_worker.py
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JS = REPO / "tools" / "catalog_worker.js"
OUT = REPO / "catalog_worker_bookmarklet.html"


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
    # En una URL javascript: un % se decodifica. El worker no usa ninguno a proposito.
    if "%" in js:
        raise SystemExit("El worker contiene '%': se rompe como bookmarklet. Quitalo.")
    href = "javascript:" + js.replace('"', "&quot;")

    OUT.write_text(
        "<!doctype html><meta charset=utf-8>"
        "<title>Catalogo worker</title>"
        "<style>body{font:15px/1.6 system-ui;margin:40px;max-width:640px}"
        "a{display:inline-block;background:#0d47a1;color:#fff;padding:10px 18px;"
        "border-radius:8px;text-decoration:none;font-weight:600}"
        "li{margin:6px 0}</style>"
        "<h1>Catalogo worker (PartSouq)</h1>"
        "<p>Arrastra este boton a la barra de marcadores:</p>"
        f'<p><a href="{href}">Catalogo worker</a></p>'
        "<ol>"
        "<li>Abri <b>partsouq.com</b> en Chrome y, si Cloudflare muestra "
        "&laquo;Verify you are human&raquo;, resolvelo a mano.</li>"
        "<li>Clic en el marcador. Abajo a la derecha aparece el cartel azul.</li>"
        "<li>Deja esa pestana abierta y a la vista. Segundo clic (o clic en el cartel) lo apaga.</li>"
        "</ol>"
        "<p>Si el cartel dice que Cloudflare pidio verificacion, vuelve a la pestana, "
        "resolvela y manda de nuevo la consulta.</p>",
        encoding="utf-8",
    )
    print(f"Escrito: {OUT}")
    print(f"Tamano del bookmarklet: {len(href):,} caracteres")
    if len(href) > 60000:
        print("OJO: algunos navegadores cortan marcadores muy largos.")


if __name__ == "__main__":
    main()
