import os
import io
import qrcode
from PIL import Image, ImageDraw, ImageFont
import textwrap
from flask import current_app

def build_qr_image_with_text(qr_url: str, nombre: str, evento: str, telefono: str, numero: int = None) -> bytes:
    qr_img = qrcode.make(qr_url).convert("RGB")
    template_path = os.path.join(current_app.static_folder, 'ticketDDA.jpg')
    
    if os.path.exists(template_path):
        try:
            bg = Image.open(template_path).convert("RGB")
            W, H = bg.size
            qr_size = 650
            qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
            qr_x = (W - qr_size) // 2
            qr_y = (H - qr_size) // 2 - 40
            bg.paste(qr_img, (qr_x, qr_y))
            
            draw = ImageDraw.Draw(bg)
            try:
                font_phone_path = os.path.join(current_app.static_folder, 'arialbd.ttf')
                font_name_path = os.path.join(current_app.static_folder, 'arial.ttf')
                font_phone = ImageFont.truetype(font_phone_path, 65) 
                font_name = ImageFont.truetype(font_name_path, 55)    
            except Exception as e:
                print(f"Error loading fonts: {e}")
                font_phone = ImageFont.load_default()
                font_name = ImageFont.load_default()
            
            def draw_centered(text, y, font, color=(0,0,0)):
                try:
                    w = draw.textlength(text, font=font)
                except:
                    w = draw.textbbox((0, 0), text, font=font)[2]
                x = (W - w) // 2
                draw.text((x, y), text, font=font, fill=color)
                return 60
            
            if numero is not None:
                draw_centered(str(numero), qr_y - 60, font_phone)
            
            text_y = qr_y + qr_size + 40
            draw_centered(telefono, text_y, font_phone)
            text_y += 80
            draw_centered(nombre, text_y, font_name)
            
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
