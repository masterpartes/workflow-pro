"""
image_to_excel.py — Extract auction data from an image → write to Excel.

Called by the Excel macro "Importar Imagen":
    WScript.Shell.Run "python tools\image_to_excel.py --image PATH"

Supports: photos of Inpart screens, scanned quotation sheets, WhatsApp images, etc.
Uses Claude API vision to extract structured data.
"""
import sys, os, json, base64, argparse
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))

from shared.config import ANTHROPIC_API_KEY
from shared.tariff_lookup import lookup_batch
from shared.excel_writer  import write_quotation


EXTRACT_PROMPT = """
You are extracting auto insurance repair quotation data from an image.

Extract the following fields (leave null if not visible):
- cotizacion_id: the quotation/pedido number
- siniestro: claim/siniestro number
- aseguradora: insurance company name
- matricula: license plate (placa)
- ano_modelo: vehicle year
- vin: 17-character VIN / chasis number
- taller: repair shop name
- armadora: vehicle make/brand
- valuador: adjuster name
- partes: list of {parte: "OE part number", descripcion: "part description"}

Rules:
- OE part numbers: alphanumeric codes (e.g. 68404445AB, 52119 0K820, A0004208503)
- Descriptions: Spanish auto part names (PARACHOQUES, PUERTA, CAPOT, etc.)
- If a field is not visible, use null
- Return ONLY valid JSON, no markdown

JSON format:
{
  "cotizacion_id": "...",
  "siniestro": "...",
  "aseguradora": "...",
  "matricula": "...",
  "ano_modelo": "...",
  "vin": "...",
  "taller": "...",
  "armadora": "...",
  "valuador": null,
  "partes": [
    {"parte": "68404445AB", "descripcion": "PARACHOQUES TRA."},
    ...
  ]
}
"""


def extract_from_image(image_path: str) -> dict:
    if not ANTHROPIC_API_KEY:
        print("[image] ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    import anthropic

    img_path = Path(image_path)
    if not img_path.exists():
        print(f"[image] File not found: {image_path}")
        sys.exit(1)

    # Determine media type
    ext = img_path.suffix.lower()
    media_type_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(ext, "image/jpeg")

    # Encode image
    image_data = base64.standard_b64encode(img_path.read_bytes()).decode("utf-8")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    print(f"[image] Sending {img_path.name} to Claude…")

    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {"type": "text", "text": EXTRACT_PROMPT},
            ],
        }]
    )

    raw = msg.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw)
    print(f"[image] Extracted: COT {data.get('cotizacion_id')} | "
          f"{len(data.get('partes', []))} parts")
    return data


def _ask_missing(data: dict) -> dict:
    """Prompt user for missing critical fields."""
    print("\n[image] Review extracted data. Press Enter to keep, or type a new value.")

    def _ask(field, label):
        current = data.get(field) or ""
        user_in = input(f"  {label} [{current}]: ").strip()
        if user_in:
            data[field] = user_in
        elif not current:
            print(f"    (left blank)")

    _ask("cotizacion_id", "Cotización #")
    _ask("siniestro",     "Siniestro")
    _ask("aseguradora",   "Aseguradora")
    _ask("matricula",     "Placa")
    _ask("ano_modelo",    "Año modelo")
    _ask("vin",           "VIN / Chasis")
    _ask("taller",        "Taller")

    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image",        required=True,       help="Path to image file")
    ap.add_argument("--no-tariffs",   action="store_true", help="Skip tariff lookup")
    ap.add_argument("--no-confirm",   action="store_true", help="Skip manual field confirmation")
    args = ap.parse_args()

    data = extract_from_image(args.image)

    if not args.no_confirm:
        data = _ask_missing(data)

    partes = data.get("partes", [])
    if not partes:
        print("[image] No parts extracted. Check the image and try again.")
        sys.exit(1)

    # Tariff lookup
    subpartidas = []
    if not args.no_tariffs:
        print(f"[tariff] Looking up {len(partes)} tariff codes…")
        descs = [p.get("descripcion", "") for p in partes]
        subpartidas = lookup_batch(descs)

    write_quotation(data, subpartidas if subpartidas else None)
    print(f"\n✓ {len(partes)} parts written to Excel from image.")


if __name__ == "__main__":
    main()
