import os
import io
import qrcode
from PIL import Image, ImageDraw, ImageFont
import textwrap
from flask import current_app

def build_qr_image_with_text(qr_url: str, nombre: str, evento: str, telefono: str, numero: int = None) -> bytes:
    qr_img = qrcode.make(qr_url).convert("RGB")
    template_path = os.path.join(current_app.static_folder, 'ticket.jpg')
    
    if os.path.exists(template_path):
        try:
            bg = Image.open(template_path).convert("RGB")
            W, H = bg.size
            # Zona negra útil del diseño: termina en la línea divisoria (y≈862).
            # Márgenes laterales alineados con el texto de la franja inferior.
            area_top, area_bottom = 50, 830
            margin_x = 108
            
            font_info = load_roboto_flex(46, weight=700)
            font_name = load_roboto_flex(50, weight=700)
            font_numero = load_roboto_flex(44, weight=700)
            tracking_info = 10
            tracking_name = 8
            
            draw = ImageDraw.Draw(bg)
            max_w = W - margin_x * 2
            nombre = fit_tracked(draw, (nombre or "").upper(), font_name, tracking_name, max_w)
            
            numero_txt = str(numero) if numero is not None else None
            gap = 28
            line_gap = 34
            h_numero = text_height(font_numero) if numero_txt else 0
            h_info = text_height(font_info)
            h_name = text_height(font_name)
            text_block = (h_numero + gap if numero_txt else 0) + gap + h_info + line_gap + h_name
            qr_max = min(max_w, area_bottom - area_top - text_block)
            # QR blanco sobre el fondo negro del diseño (el negro hace de margen)
            qr = qrcode.QRCode(border=0)
            qr.add_data(qr_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="white", back_color="black").convert("RGB")
            modules = qr.modules_count
            # QR al 90% del espacio disponible, con módulos de tamaño entero
            qr_size = max(1, round((qr_max // modules) * 0.9)) * modules
            qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
            area_top += (qr_max - qr_size) // 2
            
            y = area_top
            if numero_txt:
                draw_tracked(draw, numero_txt, (W, y), font_numero, tracking_info)
                y += h_numero + gap
            bg.paste(qr_img, ((W - qr_size) // 2, y))
            y += qr_size + gap
            draw_tracked(draw, nombre, (W, y), font_name, tracking_name)
            y += h_name + line_gap
            draw_tracked(draw, telefono or "", (W, y), font_info, tracking_info)
            
            out = io.BytesIO()
            bg.save(out, format="PNG")
            return out.getvalue()
        except Exception as e:
            print(f"Error usando template: {e}")

    qr_size = 480
    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
    margin = 24
    line_spacing = 10
    try:
        font_path = os.path.join(current_app.static_folder, 'arial.ttf')
        font_title = ImageFont.truetype(font_path, 65)
        font_text  = ImageFont.truetype(font_path, 55)
    except Exception as e:
        print(f"Error loading fonts (PROG mode): {e}")
        font_title = ImageFont.load_default()
        font_text  = ImageFont.load_default()

    title = "QR Pass"
    lines = [f"Nombre: {nombre}", f"Evento: {evento}", f"Teléfono: {telefono}"]
    if numero is not None:
        lines.append(f"Número: {numero}")

    def wrap_line(txt, font, width_px):
        max_chars = max(1, width_px // 12)
        wrapped = []
        for paragraph in txt.split("\n"):
            wrapped.extend(textwrap.wrap(paragraph, width=max_chars))
        return wrapped

    canvas_width = qr_size + margin * 2
    max_text_width = canvas_width - margin * 2

    dummy = Image.new("RGB", (10, 10))
    ddraw = ImageDraw.Draw(dummy)
    try:
        title_w, title_h = ddraw.textbbox((0, 0), title, font=font_title)[2:]
    except:
        title_w, title_h = ddraw.textsize(title, font=font_title)

    wrapped_lines, text_block_h = [], 0
    for ln in lines:
        wlines = wrap_line(ln, font_text, max_text_width)
        wrapped_lines.append(wlines)
        for wln in wlines:
            try:
                _, h = ddraw.textbbox((0, 0), wln, font=font_text)[2:]
            except:
                _, h = ddraw.textsize(wln, font=font_text)
            text_block_h += h + line_spacing
    if text_block_h > 0:
        text_block_h -= line_spacing

    canvas_height = margin + title_h + margin + qr_size + margin + text_block_h + margin
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)

    try:
        title_len = draw.textlength(title, font=font_title)
    except:
        try:
            title_len = ddraw.textbbox((0, 0), title, font=font_title)[2]
        except:
             title_len, _ = ddraw.textsize(title, font=font_title)
             
    title_x = int((canvas_width - title_len) // 2)
    y = margin
    draw.text((title_x, y), title, fill="black", font=font_title)
    y += title_h + margin

    qr_x = (canvas_width - qr_size) // 2
    canvas.paste(qr_img, (qr_x, y))
    y += qr_size + margin

    for wlines in wrapped_lines:
        for wln in wlines:
            draw.text((margin, y), wln, fill="black", font=font_text)
            try:
                _, h = ddraw.textbbox((0, 0), wln, font=font_text)[2:]
            except:
                _, h = ddraw.textsize(wln, font=font_text)
            y += h + line_spacing

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def load_roboto_flex(size, weight=250):
    try:
        font = ImageFont.truetype(os.path.join(current_app.static_folder, 'RobotoFlex.ttf'), size)
        axes = {
            b'Optical Size': min(144, max(8, size)),
            b'Weight': weight,
            b'Width': 100,
        }
        font.set_variation_by_axes([axes.get(a['name'], a['default']) for a in font.get_variation_axes()])
        return font
    except Exception as e:
        print(f"Error loading Roboto Flex: {e}")
        return ImageFont.truetype(os.path.join(current_app.static_folder, 'arial.ttf'), size)


def text_height(font):
    ascent, descent = font.getmetrics()
    return ascent + descent


def tracked_width(draw, text, font, tracking):
    if not text:
        return 0
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)


def fit_tracked(draw, text, font, tracking, max_w):
    if tracked_width(draw, text, font, tracking) <= max_w:
        return text
    while text and tracked_width(draw, text + "…", font, tracking) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def draw_tracked(draw, text, pos, font, tracking, color=(255, 255, 255)):
    """Dibuja texto centrado horizontalmente en pos[0] (ancho) con letter spacing."""
    W, y = pos
    x = (W - tracked_width(draw, text, font, tracking)) / 2
    for ch in text:
        draw.text((x, y), ch, font=font, fill=color)
        x += draw.textlength(ch, font=font) + tracking
