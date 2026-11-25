"""presupuesto.py — imagen de presupuesto para el cliente (diseño de la skill
master-partes-presupuesto, sin cambios de estilo). Sin columna de número de parte,
sin costos ni fuentes: es para reenviar al cliente tal cual."""
import base64
import io
import os
from datetime import date
from PIL import Image, ImageDraw, ImageFont

LOGO_B64 = "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"

_FUENTES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
]


def _font(bold, size):
    for reg, neg in _FUENTES:
        p = neg if bold else reg
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render(ITEMS, OUTPUT_PATH, CLIENTE="", VEHICULO="", NUMERO_PRESUPUESTO="0001",
           FECHA=None, MONEDA="$",
           PIE="Precios no incluyen IVA · Entrega: 20 días (importación)"):
    """ITEMS = [(descripcion, marca, precio), ...]. Devuelve OUTPUT_PATH."""
    FECHA = FECHA or date.today().strftime("%d/%m/%Y")

    NAVY = (23, 37, 58)
    STEEL_BLUE = (47, 130, 178)
    WHITE = (255, 255, 255)
    TEXT_DARK = (35, 39, 46)
    TEXT_MUTED = (120, 128, 138)
    ROW_ALT = (243, 246, 249)
    BORDER = (226, 230, 236)

    f_h1 = _font(True, 34)
    f_h2 = _font(False, 20)
    f_header = _font(True, 22)
    f_body = _font(False, 23)
    f_body_bold = _font(True, 23)
    f_small = _font(False, 17)

    col_widths = [60, 560, 210, 170]
    MARGIN = 48
    W = sum(col_widths) + MARGIN * 2
    row_h = 60
    table_header_h = 58
    top_h = 168 if VEHICULO else 168
    total_h = 56
    footer_h = 70
    H = top_h + table_header_h + row_h * len(ITEMS) + total_h + footer_h

    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)


    def text_w(txt, font):
        b = d.textbbox((0, 0), txt, font=font)
        return b[2] - b[0], b[3] - b[1], b[1]


    d.rectangle([0, 0, W, 6], fill=STEEL_BLUE)

    logo_bytes = base64.b64decode(LOGO_B64)
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
    logo_h = 64
    logo_w = int(logo.width * logo_h / logo.height)
    logo_r = logo.resize((logo_w, logo_h), Image.LANCZOS)
    img.paste(logo_r, (MARGIN, 34), logo_r)

    title = "PRESUPUESTO"
    tw, th, toff = text_w(title, f_h1)
    d.text((W - MARGIN - tw, 32), title, font=f_h1, fill=NAVY)

    meta = f"N.º {NUMERO_PRESUPUESTO}    |    Fecha: {FECHA}"
    tw, th, toff = text_w(meta, f_h2)
    d.text((W - MARGIN - tw, 76), meta, font=f_h2, fill=TEXT_MUTED)

    info_y = 120
    d.line([MARGIN, info_y - 12, W - MARGIN, info_y - 12], fill=BORDER, width=1)
    d.text((MARGIN, info_y), f"Cliente:  {CLIENTE}", font=f_body, fill=TEXT_DARK)
    if VEHICULO:
        tw, th, toff = text_w(f"Vehículo:  {VEHICULO}", f_body)
        d.text((W - MARGIN - tw, info_y), f"Vehículo:  {VEHICULO}", font=f_body, fill=TEXT_DARK)

    y = top_h

    headers = ["N°", "DESCRIPCIÓN", "MARCA", "PRECIO"]
    align = ["c", "l", "c", "c"]
    d.rectangle([MARGIN, y, W - MARGIN, y + table_header_h], fill=NAVY)
    cx = MARGIN
    for i, htxt in enumerate(headers):
        cw = col_widths[i]
        tw, th, toff = text_w(htxt, f_header)
        tx = cx + 18 if align[i] == "l" else cx + (cw - tw) / 2
        ty = y + (table_header_h - th) / 2 - toff
        d.text((tx, ty), htxt, font=f_header, fill=WHITE)
        cx += cw
    y += table_header_h

    total = 0
    for idx, (desc, marca, precio) in enumerate(ITEMS):
        total += precio
        fill = WHITE if idx % 2 == 0 else ROW_ALT
        d.rectangle([MARGIN, y, W - MARGIN, y + row_h], fill=fill)
        cx = MARGIN

        n_txt = str(idx + 1)
        tw, th, toff = text_w(n_txt, f_body)
        d.text((cx + (col_widths[0] - tw) / 2, y + (row_h - th) / 2 - toff), n_txt, font=f_body, fill=TEXT_MUTED)
        cx += col_widths[0]

        tw, th, toff = text_w(desc, f_body)
        d.text((cx + 18, y + (row_h - th) / 2 - toff), desc, font=f_body, fill=TEXT_DARK)
        cx += col_widths[1]

        tw, th, toff = text_w(marca, f_body)
        d.text((cx + (col_widths[2] - tw) / 2, y + (row_h - th) / 2 - toff), marca, font=f_body, fill=TEXT_DARK)
        cx += col_widths[2]

        ptxt = f"{MONEDA}{precio:,.2f}"
        tw, th, toff = text_w(ptxt, f_body_bold)
        d.text((cx + (col_widths[3] - tw) / 2 - 8, y + (row_h - th) / 2 - toff), ptxt, font=f_body_bold, fill=STEEL_BLUE)
        cx += col_widths[3]

        y += row_h
        d.line([MARGIN, y, W - MARGIN, y], fill=BORDER, width=1)

    d.rectangle([MARGIN, y, W - MARGIN, y + total_h], fill=NAVY)
    label = "TOTAL"
    label_x = MARGIN + col_widths[0] + col_widths[1] + col_widths[2] - 20
    tw, th, toff = text_w(label, f_header)
    d.text((label_x - tw, y + (total_h - th) / 2 - toff), label, font=f_header, fill=WHITE)
    ttxt = f"{MONEDA}{total:,.2f}"
    tw, th, toff = text_w(ttxt, f_header)
    tx = MARGIN + col_widths[0] + col_widths[1] + col_widths[2] + (col_widths[3] - tw) / 2 - 8
    d.text((tx, y + (total_h - th) / 2 - toff), ttxt, font=f_header, fill=WHITE)
    y += total_h

    d.rectangle([0, y, W, H], fill=WHITE)
    footer_txt = PIE
    d.text((MARGIN, y + 22), footer_txt, font=f_small, fill=TEXT_MUTED)
    d.rectangle([0, H - 4, W, H], fill=STEEL_BLUE)

    img.save(OUTPUT_PATH)
    return OUTPUT_PATH
