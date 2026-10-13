"""
ops.py — escrituras del bot sobre workflow-pro (Supabase vía PostgREST).

Reglas (BRIEF_MASTER_PARTES_v3.md §5, §8):
  * Cada escritura es de dos pasos: confirmar=False devuelve una vista previa,
    confirmar=True escribe. El bot muestra la vista previa y espera "sí".
  * Toda escritura deja una fila en bot_log (antes/después) para poder deshacer.
  * Los archivos solo se suben desde las carpetas permitidas (adjuntos de
    Telegram), con extensiones de imagen/PDF. Nunca un archivo arbitrario.
"""
from __future__ import annotations

import datetime as _dt
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Optional

import httpx

from shared.config import SUPABASE_URL, SUPABASE_ANON_KEY

USUARIOS = {"alejandro": "Alejandro", "santiago": "Santiago"}
CATEGORIAS = ("flete_origen", "courier", "aduana_declaracion",
              "transporte_local", "combustible", "cliente", "general")
CATEGORIAS_SANTIAGO = ("transporte_local", "combustible", "cliente")
ESTADOS = ("adjudicado", "comprado", "transito", "en_bodega",
           "en_aduana", "enviado_cliente", "entregado")
EXT_OK = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"}
MAX_BYTES = 20 * 1024 * 1024
QUITO = _dt.timezone(_dt.timedelta(hours=-5))


class OpsError(RuntimeError):
    pass


def hoy_quito() -> str:
    return _dt.datetime.now(QUITO).date().isoformat()


def usuario_valido(u: str) -> str:
    v = USUARIOS.get((u or "").strip().lower())
    if not v:
        raise OpsError(f"usuario desconocido '{u}'. Debe ser Alejandro o Santiago.")
    return v


# ── HTTP ───────────────────────────────────────────────────────────────────────

def _h(extra: Optional[dict] = None) -> dict:
    if not SUPABASE_ANON_KEY:
        raise OpsError("SUPABASE_ANON_KEY no está en .env")
    h = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    if extra:
        h.update(extra)
    return h


async def select(c: httpx.AsyncClient, table: str, params: dict) -> list:
    r = await c.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=_h(), params=params)
    if r.status_code != 200:
        raise OpsError(f"leer {table}: HTTP {r.status_code} {r.text[:200]}")
    return r.json()


async def insert(c: httpx.AsyncClient, table: str, row: dict) -> dict:
    r = await c.post(f"{SUPABASE_URL}/rest/v1/{table}", json=row,
                     headers=_h({"Prefer": "return=representation"}))
    if r.status_code not in (200, 201):
        raise OpsError(f"insertar en {table}: HTTP {r.status_code} {r.text[:300]}")
    return r.json()[0]


async def update(c: httpx.AsyncClient, table: str, row_id: str, changes: dict) -> dict:
    r = await c.patch(f"{SUPABASE_URL}/rest/v1/{table}", json=changes,
                      params={"id": f"eq.{row_id}"},
                      headers=_h({"Prefer": "return=representation"}))
    if r.status_code != 200 or not r.json():
        raise OpsError(f"actualizar {table} {row_id}: HTTP {r.status_code} {r.text[:300]}")
    return r.json()[0]


async def log(c: httpx.AsyncClient, usuario: str, tool: str, tabla: str,
              fila_id: str, antes: Optional[dict], despues: Optional[dict]) -> None:
    await insert(c, "bot_log", {"usuario": usuario, "tool": tool, "tabla": tabla,
                                "fila_id": fila_id, "antes": antes, "despues": despues})


# ── Archivos ───────────────────────────────────────────────────────────────────

def _dirs_permitidos() -> list[Path]:
    env = os.environ.get("BOT_ATTACH_DIRS", "")
    dirs = [Path(p) for p in env.split(";") if p.strip()]
    dirs.append(Path.home() / ".claude" / "channels" / "telegram")
    # adjuntos que el dueño manda desde la app de Claude (se copian acá)
    dirs.append(Path(__file__).resolve().parents[2] / "inbox")
    return [d.resolve() for d in dirs]


def validar_archivo(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not any(d == p or d in p.parents for d in _dirs_permitidos()):
        raise OpsError("archivo fuera de las carpetas de adjuntos permitidas; "
                       "no se sube.")
    if p.suffix.lower() not in EXT_OK:
        raise OpsError(f"tipo de archivo no permitido: {p.suffix}")
    if not p.is_file():
        raise OpsError(f"no existe el archivo: {p.name}")
    if p.stat().st_size > MAX_BYTES:
        raise OpsError("archivo de más de 20 MB")
    return p


async def subir(c: httpx.AsyncClient, p: Path, bucket: str, carpeta: str) -> str:
    """Sube el archivo. Devuelve URL pública (bucket 'uploads') o ruta (privado)."""
    nombre = f"{carpeta}/{hoy_quito()}_{uuid.uuid4().hex[:8]}{p.suffix.lower()}"
    ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    r = await c.post(f"{SUPABASE_URL}/storage/v1/object/{bucket}/{nombre}",
                     content=p.read_bytes(),
                     headers=_h({"Content-Type": ctype, "x-upsert": "false"}))
    if r.status_code not in (200, 201):
        raise OpsError(f"subir archivo: HTTP {r.status_code} {r.text[:200]}")
    if bucket == "uploads":
        return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{nombre}"
    return f"{bucket}/{nombre}"
