"""
avk_live.py — precios AVK en vivo, via la cola de trabajos.

Por que no se consulta avkparts.lt directamente desde aca: Cloudflare solo deja
pasar al Chrome real del dueno. httpx, Playwright y el panel de Claude se comen
el desafio (brief seccion 5, verificado otra vez el 21-sep-2026). Asi que este
modulo NO navega: encola el numero de parte y espera a que el worker que corre
dentro de esa pestana escriba el resultado.

Si el worker no esta corriendo, esto lo dice en un segundo en vez de colgarse
noventa: para eso existe la tabla avk_worker.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

try:
    from shared.config import SUPABASE_URL, SUPABASE_ANON_KEY
except ImportError:                                   # el worker de Railway no tiene tools/ en el path
    import os
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

_OE_OK = re.compile(r"[^A-Z0-9]")
WORKER_VIVO_S = 90          # margen sobre el POLL_MS de 5 s del worker
ESPERA_S      = 90
INTERVALO_S   = 2.0


class AvkError(RuntimeError):
    pass


def normalizar_oe(oe: str) -> str:
    """
    Deja solo A-Z0-9.

    No es cosmetica: el numero de parte llega, al final de la cadena, de un
    mensaje de Telegram. Saneado aca, lo unico que puede viajar a la URL de
    busqueda son letras y digitos.
    """
    return _OE_OK.sub("", (oe or "").upper())


def _headers() -> dict:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise AvkError("SUPABASE_URL / SUPABASE_ANON_KEY no estan configurados.")
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def worker_vivo(client: httpx.AsyncClient) -> tuple[bool, Optional[str]]:
    r = await client.get(f"{SUPABASE_URL}/rest/v1/avk_worker",
                         params={"select": "last_seen,note", "id": "eq.1", "limit": "1"})
    if r.status_code != 200 or not r.json():
        return False, "no se pudo leer avk_worker (¿falta la migracion 006?)"
    visto = datetime.fromisoformat(r.json()[0]["last_seen"].replace("Z", "+00:00"))
    edad = datetime.now(timezone.utc) - visto
    if edad > timedelta(seconds=WORKER_VIVO_S):
        return False, f"ultimo latido hace {int(edad.total_seconds())} s"
    return True, r.json()[0].get("note")


async def lookup_avk(oes: list[str], espera_s: int = ESPERA_S) -> dict:
    """
    Devuelve {"ok": bool, "partes": {OE: {...}}, "error": str|None}.

    Cada parte trae: ofertas ordenadas por precio, la mas barata genuina, la mas
    barata alterna, y el peso que declara AVK cuando lo publica.
    """
    limpios = [normalizar_oe(o) for o in oes]
    limpios = [o for o in limpios if o]
    if not limpios:
        return {"ok": False, "error": "No quedo ningun numero de parte valido."}

    async with httpx.AsyncClient(headers=_headers(), timeout=20.0) as client:
        vivo, nota = await worker_vivo(client)
        if not vivo:
            return {
                "ok": False,
                "worker_caido": True,
                "error": (
                    "El worker de AVK no esta corriendo (" + (nota or "sin latido") + "). "
                    "Hay que abrir avkparts.lt en Chrome y hacer clic en el marcador "
                    "'AVK worker'. Sin eso no hay precios de AVK."
                ),
            }

        r = await client.post(
            f"{SUPABASE_URL}/rest/v1/avk_job",
            json=[{"oe": o} for o in limpios],
            headers={**_headers(), "Prefer": "return=representation"},
        )
        if r.status_code not in (200, 201):
            raise AvkError(f"No se pudieron encolar los trabajos: {r.status_code} {r.text[:200]}")
        ids = [fila["id"] for fila in r.json()]

        limite = asyncio.get_event_loop().time() + espera_s
        pendientes = set(ids)
        filas: dict[int, dict] = {}

        while pendientes and asyncio.get_event_loop().time() < limite:
            await asyncio.sleep(INTERVALO_S)
            q = await client.get(
                f"{SUPABASE_URL}/rest/v1/avk_job",
                params={"select": "id,oe,status,result,error",
                        "id": f"in.({','.join(str(i) for i in ids)})"},
            )
            if q.status_code != 200:
                continue
            for fila in q.json():
                if fila["status"] in ("done", "error"):
                    filas[fila["id"]] = fila
                    pendientes.discard(fila["id"])

        partes: dict[str, dict] = {}
        for i, oe in zip(ids, limpios):
            fila = filas.get(i)
            if fila is None:
                partes[oe] = {"ok": False, "error": f"sin respuesta en {espera_s} s"}
                continue
            if fila["status"] == "error":
                err = fila.get("error") or "error"
                partes[oe] = {
                    "ok": False,
                    "error": ("AVK pidio verificacion de Cloudflare; hay que abrir la "
                              "pestana y resolverla a mano."
                              if "cloudflare" in err else err),
                }
                continue

            res = fila.get("result")
            ofertas = res.get("ofertas", []) if isinstance(res, dict) else (res or [])
            ofertas = [o for o in ofertas if o.get("price_eur") is not None]
            ofertas.sort(key=lambda o: o["price_eur"])
            gen = [o for o in ofertas if o.get("calidad") == "genuino"]
            alt = [o for o in ofertas if o.get("calidad") == "alterno"]
            partes[oe] = {
                "ok": bool(ofertas),
                "ofertas": ofertas,
                "genuino": gen[0] if gen else None,
                "alterno": alt[0] if alt else None,
                "peso_kg": res.get("peso_kg") if isinstance(res, dict) else None,
                "fuente": "AVK avkparts.lt",
            }
            if not ofertas:
                partes[oe]["error"] = "AVK no devolvio precios para este codigo."

        return {"ok": True, "partes": partes}
