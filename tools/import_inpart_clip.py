"""
import_inpart_clip.py — Read Inpart bookmarklet JSON from clipboard → Excel.

Flow:
  1. Open Inpart, click Visualizar on a quotation
  2. Click "Inpart: Extraer Cotización" bookmarklet
  3. Click INPART button in Excel → this script runs
  4. Reads JSON from clipboard, runs tariff lookup, writes to Excel
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))

from shared.tariff_lookup import lookup_batch
from shared.excel_writer import write_quotation


def _read_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception as e:
        print(f"[ERROR] No se pudo leer el portapapeles: {e}")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-tariffs", action="store_true", help="Skip tariff lookup")
    args = ap.parse_args()

    print("Leyendo portapapeles…")
    raw = _read_clipboard().strip()

    if not raw:
        print("[ERROR] El portapapeles está vacío.")
        print("        Haz clic en el bookmarklet 'Inpart: Extraer Cotización' primero.")
        input("\nPresiona Enter para cerrar…")
        sys.exit(1)

    # Support single quotation (dict) or multiple (list)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON inválido: {e}")
        print("        Asegúrate de haber usado el bookmarklet Inpart (no el de AVK).")
        input("\nPresiona Enter para cerrar…")
        sys.exit(1)

    # Normalize to list
    if isinstance(data, dict):
        quotations = [data]
    elif isinstance(data, list):
        quotations = data
    else:
        print("[ERROR] Formato JSON inesperado.")
        input("\nPresiona Enter para cerrar…")
        sys.exit(1)

    total_parts = 0
    for q in quotations:
        partes = q.get("partes", [])
        if not partes:
            print(f"  COT {q.get('cotizacion_id','?')}: sin piezas — omitida")
            continue

        print(f"\nCOT {q.get('cotizacion_id')} | {q.get('armadora','')} {q.get('ano_modelo','')} | "
              f"{q.get('aseguradora','')} | {q.get('matricula','')}")
        print(f"  VIN: {q.get('vin','')}")
        print(f"  {len(partes)} pieza(s):")
        for p in partes:
            print(f"    {p.get('parte',''):<25} {p.get('descripcion','')}")

        # Tariff lookup
        subpartidas = []
        if not args.no_tariffs:
            print(f"\n  Buscando aranceles…")
            descs = [p.get("descripcion", "") for p in partes]
            subpartidas = lookup_batch(descs)
        else:
            subpartidas = [{"subpartida": None, "arancel": None}] * len(partes)

        write_quotation(q, subpartidas)
        total_parts += len(partes)
        print(f"  ✓ Escrito en Excel")

    print(f"\n✓ Listo: {len(quotations)} cotización(es), {total_parts} pieza(s) importadas.")
    input("\nPresiona Enter para cerrar…")


if __name__ == "__main__":
    main()
