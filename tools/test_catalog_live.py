"""Prueba offline de catalog_live.emparejar / formatear / a_partes_quote con datos REALES del
diagrama Headlamp del Montero (VIN MMBGUKS50PH001101, capturados de PartSouq el 18-oct-2026)
y un LLM simulado. Uso:  python tools/test_catalog_live.py"""
import json, sys, types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "agent")); sys.path.insert(0, str(REPO / "tools"))
try:
    import httpx  # noqa: F401
except ImportError:                                   # para correr en una VM sin dependencias
    sys.modules["httpx"] = types.ModuleType("httpx")
import catalog_live as C

def pz(n, d, cal, q="1", rep=None):
    return {"numero": n, "descripcion": d, "callout": cal, "cantidad": q,
            "aplicabilidad": "01.12.2021 - 03.09.2022 GUPML;GUPMLW;GUPML1NH", "reemplazo": rep}
HEAD = [pz("8301D623", "BODY,HEADLAMP,LH", "80003L", rep="26064W530P"), pz("8301D624", "HEADLIGHT HOUSING", "80003R", rep="26014W530P"),
        pz("8301D475", "COVER,HEADLAMP BULB SOCKET", "80025B", "2"), pz("8301D437", "HEADLIGHT", "80030AL", rep="26060W570P"),
        pz("8301D438", "HEADLIGHT", "80030AR", rep="26010W570P"), pz("8301D474", "GASKET,HEADLAMP", "80052", "2"),
        pz("8301D620", "HARNESS,HEADLAMP,LH", "83085L"), pz("8301D620", "HARNESS,HEADLAMP,RH", "83085R")]
RES = {"vehiculo": {"catalogo": "mitsubishi", "modelo": "Montero / Pajero / Nativa", "anio": "2022", "codigo": "KS5W"},
       "diagramas": [{"grupo": "Body, car glass", "nombre": "Headlamp", "piezas": HEAD}],
       "pedidos": [{"descripcion": "faro derecho", "estado": "ok", "diagramas": [0]},
                   {"descripcion": "cubo de rueda", "estado": "sin_mapa", "diagramas": []},
                   {"descripcion": "faro izquierdo", "estado": "ok", "diagramas": [0]},
                   {"descripcion": "guardafango der", "estado": "sin_diagrama", "diagramas": []}]}
DESC = [p["descripcion"] for p in RES["pedidos"]]

def llm_bueno(prompt):
    assert "<datos>" in prompt and "8301D438" in prompt
    return "Claro:\n" + json.dumps([{"i": 0, "numero": "8301D438", "confianza": "alta", "motivo": "HEADLIGHT callout 80030AR = derecho"},
                                    {"i": 2, "numero": "8301D437", "confianza": "media", "motivo": "callout L"}])
def llm_inventa(prompt):
    return json.dumps([{"i": 0, "numero": "9999ZZZZ", "confianza": "alta", "motivo": "x"},
                       {"i": 2, "numero": None, "confianza": "baja", "motivo": "ninguna"}])

r = C.emparejar(RES, DESC, llm_bueno)
assert r[0]["numero"] == "8301D438" and r[0]["confianza"] == "alta" and "reemplazo 26010W570P" in r[0]["nota"], r[0]
assert r[1]["numero"] is None and "grupo" in r[1]["nota"] and r[3]["numero"] is None
assert r[2]["numero"] == "8301D437"
r2 = C.emparejar(RES, DESC, llm_inventa)
assert r2[0]["numero"] is None and "descartado" in r2[0]["nota"], r2[0]      # numero inventado: se descarta
print(C.formatear(RES["vehiculo"], r)); print()
q = C.a_partes_quote(r, {"faro derecho": 1, "faro izquierdo": 2}); print(q)
assert [x["parte"] for x in q] == ["8301D438", "8301D437"] and q[1]["cantidad"] == 2
assert C.marca_de(RES) == "mitsubishi"
assert C.normalizar_vin("mmbg uks50ph001101") == "MMBGUKS50PH001101" and C.normalizar_vin("MMBGUKS50PH00110I") == ""
assert C.limpiar_descripciones(["faro\nder\x00echo", "  ", "x" * 500])[0] == "faro der echo" and len(C.limpiar_descripciones(["x" * 500])[0]) == 80
print("\nTODO OK")
