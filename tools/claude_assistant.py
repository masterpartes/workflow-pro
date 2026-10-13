"""
claude_assistant.py — Claude AI assistant embedded in Excel.

Called by the VBA macro "Consultar Claude":
    python tools\claude_assistant.py --row R --question "..."

Reads the part row context from Excel (parte, descripcion, VIN, etc.),
sends it to Claude Haiku along with the user's question, and prints the answer.

Use cases:
  - "What is the tariff code for this part?"
  - "What BMW model is VIN WBAFG8107DD000001?"
  - "Translate this description to Spanish"
  - "Is 68404445AB the correct bumper part for a 2019 Ram 1500?"
  - "Suggest a FOB price for this part in USD"
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(__file__))

from shared.config import ANTHROPIC_API_KEY, EXCEL_FILE
from shared.excel_writer import _open_wb, COL

SYSTEM_PROMPT = """You are an expert assistant for an auto parts import quotation system in Ecuador.
You help users with:
- Identifying correct OEM part numbers and descriptions
- Finding Ecuador customs tariff codes (subpartidas arancelarias) and arancel percentages
- Translating and standardizing part descriptions to Spanish
- Identifying vehicle models from VIN numbers
- Estimating FOB prices for auto parts
- Verifying part compatibility with specific vehicles

Be concise and direct. When suggesting tariff codes, give the 10-digit subpartida and the arancel % (IVA not included).
When answering in Spanish, use technical automotive terminology.
"""


def _get_row_context(row: int) -> dict:
    """Read part row data from Excel."""
    try:
        wb = _open_wb()
        ws = wb.sheets["COTIZACION"]

        parte       = ws.cells(row, COL["PARTE"]).value or ""
        descripcion = ws.cells(row, COL["DESCRIPCION"]).value or ""
        subpartida  = ws.cells(row, COL["SUBPARTIDA"]).value or ""
        arancel     = ws.cells(row, COL["ARANCEL"]).value or ""
        fob         = ws.cells(row, COL["FOB"]).value or ""
        oem_msrp    = ws.cells(row, COL["OEM_MSRP"]).value or ""
        oem_price   = ws.cells(row, COL["OEM_PRECIO"]).value or ""

        # Walk up to find VIN from the auction header
        vin = ""
        armadora = ""
        for r in range(row - 1, 1, -1):
            v = ws.cells(r, 1).value
            if v and str(v).startswith("COT."):
                header = str(v)
                import re
                m = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", header, re.I)
                if m:
                    vin = m.group(0)
                break

        return {
            "parte": parte, "descripcion": descripcion,
            "subpartida": subpartida, "arancel": arancel,
            "fob": fob, "oem_msrp": oem_msrp, "oem_price": oem_price,
            "vin": vin, "row": row,
        }
    except Exception as e:
        return {"error": str(e)}


def _build_context_text(ctx: dict) -> str:
    lines = ["Current part row context:"]
    if ctx.get("parte"):        lines.append(f"  Part number: {ctx['parte']}")
    if ctx.get("descripcion"):  lines.append(f"  Description: {ctx['descripcion']}")
    if ctx.get("vin"):          lines.append(f"  VIN: {ctx['vin']}")
    if ctx.get("subpartida"):   lines.append(f"  Subpartida: {ctx['subpartida']}")
    if ctx.get("arancel"):      lines.append(f"  Arancel: {ctx['arancel']}%")
    if ctx.get("fob"):          lines.append(f"  FOB price: ${ctx['fob']}")
    if ctx.get("oem_msrp"):     lines.append(f"  OEM MSRP: ${ctx['oem_msrp']}")
    if ctx.get("oem_price"):    lines.append(f"  OEM price: ${ctx['oem_price']}")
    return "\n".join(lines)


def ask_claude(question: str, context_text: str = "") -> str:
    if not ANTHROPIC_API_KEY:
        return "ERROR: ANTHROPIC_API_KEY not set in .env"

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_msg = ""
    if context_text:
        user_msg = context_text + "\n\n"
    user_msg += question

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )
    return msg.content[0].text


def interactive_mode(row: int):
    """Keep asking questions until the user types 'salir'."""
    ctx = _get_row_context(row) if row else {}
    context_text = _build_context_text(ctx) if ctx and not ctx.get("error") else ""

    if context_text:
        print("\n" + context_text)

    print("\n" + "=" * 60)
    print("  ASISTENTE CLAUDE — escribe 'salir' para cerrar")
    print("=" * 60 + "\n")

    while True:
        try:
            question = input("Tu pregunta: ").strip()
        except EOFError:
            break
        if not question or question.lower() in ("salir", "exit", "quit"):
            break

        print("\nClaude:")
        answer = ask_claude(question, context_text)
        print(answer)
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--row",      type=int, default=0,  help="Excel row number of the selected part")
    ap.add_argument("--question", default="",            help="Question to ask (non-interactive mode)")
    args = ap.parse_args()

    if args.question:
        # Single-shot mode (called programmatically)
        ctx = _get_row_context(args.row) if args.row else {}
        context_text = _build_context_text(ctx) if ctx and not ctx.get("error") else ""
        print(ask_claude(args.question, context_text))
    else:
        # Interactive mode
        interactive_mode(args.row)
        input("\nPresiona Enter para cerrar…")


if __name__ == "__main__":
    main()
