"""
import_manual.py — Manual text input → Excel quotation.

Called by the Excel macro "Importar Manual":
    WScript.Shell.Run "python tools\import_manual.py"

Workflow:
  1. A command window opens.
  2. Fill in quotation header fields (press Enter to skip optional ones).
  3. Paste your parts list when prompted.
     Format — one part per line, tab OR pipe OR 2+ spaces between number and description:
         68404445AB      PARACHOQUES TRA.
         52119-0K820     FAROLA DELANTERA
         A0004208503     BOMBA DE AGUA
     Finish by typing a blank line or pressing Ctrl+Z (EOF).
  4. Tariff lookup runs automatically.
  5. Excel is updated.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

from shared.tariff_lookup import lookup_batch
from shared.excel_writer import write_quotation


# ── helpers ───────────────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    disp = f" [{default}]" if default else ""
    try:
        val = input(f"  {prompt}{disp}: ").strip()
    except EOFError:
        val = ""
    return val if val else default


def _parse_parts(raw: str) -> list[dict]:
    """
    Parse a block of text into [{parte, descripcion}].

    Accepts tab, pipe, or 2+ spaces as delimiter.
    Lines that look like headers/totals are skipped.
    """
    parts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Try tab first, then pipe, then 2+ spaces
        if "\t" in line:
            cols = line.split("\t", 1)
        elif "|" in line:
            cols = line.split("|", 1)
        else:
            cols = re.split(r"\s{2,}", line, maxsplit=1)

        if len(cols) < 2:
            # Single token — treat as part number with no description
            pn = cols[0].strip()
            if pn:
                parts.append({"parte": pn, "descripcion": ""})
            continue

        pn   = cols[0].strip()
        desc = cols[1].strip()

        if not pn:
            continue
        # Skip obvious header rows (no alphanumeric part number)
        if not re.search(r"[A-Z0-9]", pn, re.I):
            continue

        parts.append({"parte": pn, "descripcion": desc})
    return parts


def _read_parts_from_input() -> list[dict]:
    """
    Read multi-line parts input.
    User can paste a block; finish with a blank line or Ctrl+Z / Ctrl+D.
    """
    print()
    print("  Pega la lista de piezas (PARTE <tab> DESCRIPCION, una por línea).")
    print("  Termina con una línea en blanco + Enter:\n")

    lines = []
    blank_streak = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            blank_streak += 1
            if blank_streak >= 1 and lines:
                break
        else:
            blank_streak = 0
            lines.append(line)

    return _parse_parts("\n".join(lines))


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  IMPORTAR COTIZACIÓN MANUAL")
    print("  (Enter para omitir campos opcionales)")
    print("=" * 60)
    print()

    print("── Datos de la cotización ──")
    cotizacion_id = _ask("Nº Cotización *")
    siniestro     = _ask("Siniestro")
    aseguradora   = _ask("Aseguradora")
    matricula     = _ask("Placa / Matrícula")
    ano_modelo    = _ask("Año modelo")
    vin           = _ask("VIN / Chasis")
    taller        = _ask("Taller")
    armadora      = _ask("Marca (armadora)")
    valuador      = _ask("Valuador")

    if not cotizacion_id:
        print("\n[ERROR] El número de cotización es obligatorio.")
        input("Presiona Enter para cerrar…")
        sys.exit(1)

    # Parts input
    print()
    print("── Lista de piezas ──")
    partes = _read_parts_from_input()

    if not partes:
        print("\n[ERROR] No se ingresaron piezas.")
        input("Presiona Enter para cerrar…")
        sys.exit(1)

    print(f"\n  {len(partes)} pieza(s) leída(s):")
    for p in partes:
        print(f"    {p['parte']:<20} {p['descripcion']}")

    # Tariff lookup
    print(f"\n[tariff] Buscando {len(partes)} aranceles…")
    descs = [p["descripcion"] for p in partes]
    subpartidas = lookup_batch(descs)

    # Build quotation dict
    quotation = {
        "cotizacion_id": cotizacion_id,
        "siniestro":     siniestro,
        "aseguradora":   aseguradora,
        "matricula":     matricula,
        "ano_modelo":    ano_modelo,
        "vin":           vin,
        "taller":        taller,
        "armadora":      armadora,
        "valuador":      valuador,
        "partes":        partes,
    }

    write_quotation(quotation, subpartidas)

    print(f"\n✓ {len(partes)} pieza(s) escritas en Excel — COT {cotizacion_id}")
    print()
    input("Presiona Enter para cerrar…")


if __name__ == "__main__":
    main()
