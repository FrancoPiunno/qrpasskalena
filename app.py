from flask import Flask, render_template, request, redirect, url_for, send_file, make_response, flash
import os
import io
# Ready for merge: v2 -> main
import base64
import uuid
import qrcode
import requests
import json
import re
import unicodedata
from datetime import timedelta, datetime
from functools import wraps
from collections import Counter

import firebase_admin
from firebase_admin import credentials, firestore, auth
from google.cloud import firestore as gcf_firestore  # para @transactional

from PIL import Image, ImageDraw, ImageFont
import textwrap

# =========================
# App & Config
# =========================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY", "TU_API_KEY_WEB")
# En Render podés setear EXTERNAL_BASE_URL (recomendado). Si no, intenta con RENDER_EXTERNAL_URL.
EXTERNAL_BASE_URL = os.environ.get("EXTERNAL_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL")

# =========================
# Firebase Admin (clave desde env o archivo)
# =========================
def load_firebase_credentials():
    env_key = os.environ.get("FIREBASE_KEY_JSON")
    if env_key:
        try:
            # Acepta JSON crudo o base64
            txt = env_key if env_key.strip().startswith("{") else base64.b64decode(env_key).decode("utf-8")
            data = json.loads(txt)
            return credentials.Certificate(data)
        except Exception as e:
            # Fallback a archivo
            print("WARN: No pude parsear FIREBASE_KEY_JSON, usando firebase_key.json. Error:", e)
    # Si no hay env o falló, usar archivo en el repo
    return credentials.Certificate("firebase_key.json")

# Evitar doble inicialización
if not firebase_admin._apps:
    cred = load_firebase_credentials()
    firebase_admin.initialize_app(cred)

db = firestore.client()

# =========================
# Helpers de autenticación
# =========================
def verify_session_cookie(req):
    session_cookie = req.cookies.get("session")
    if not session_cookie:
        return None
    try:
        decoded = auth.verify_session_cookie(session_cookie, check_revoked=True)
        return decoded  # dict con uid, email, etc.
    except Exception:
        return None

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = verify_session_cookie(request)
        if not user:
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_user():
    # Para usar {% if user %} en todos los templates
    return dict(user=verify_session_cookie(request))

# =========================
# Helpers QR / URLs
# =========================
def build_qr_image_with_text(qr_url: str, nombre: str, evento: str, telefono: str) -> bytes:
    """
    Genera un PNG con el QR (centro) y los textos abajo.
    Si existe 'static/ticket_template.png', usa eso de fondo.
    Si no, usa fondo blanco generado.
    """
    # 1) QR base
    qr_img = qrcode.make(qr_url).convert("RGB")
    
    # Check for template
    template_path = os.path.join(app.root_path, 'static', 'ticket_template.png')
    
    if os.path.exists(template_path):
        # --- MODO TEMPLATE ---
        try:
            bg = Image.open(template_path).convert("RGB")
            W, H = bg.size
            
            # NUEVO TEMPLATE (1080 x 1445 aprox)
            # Caja blanca estimada: 900px ancho? No, el usuario dijo "entra bien".
            # Ajustamos proporcionalmente. Antes era 420 para 740W.
            # Ahora 1080W. Probemos QR de 650px.
            qr_size = 650
            qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
            
            # Posición: Centrado horizontal
            qr_x = (W - qr_size) // 2
            
            # Vertical: El centro visual de la caja blanca.
            # En el diseño tipo "polaroid", la caja suele estar centrada ligeramente arriba.
            # H/2 - offset. Probemos offset de 40px hacia arriba desde el centro (antes 150).
            qr_y = (H - qr_size) // 2 - 40
            
            bg.paste(qr_img, (qr_x, qr_y))
            
            # Configurar fuentes (más grandes para alta resolución)
            draw = ImageDraw.Draw(bg)
            try:
                # Load bundled fonts from static folder for Render compatibility
                font_phone_path = os.path.join(app.root_path, 'static', 'arialbd.ttf')
                font_name_path = os.path.join(app.root_path, 'static', 'arial.ttf')
                
                font_phone = ImageFont.truetype(font_phone_path, 65) 
                font_name = ImageFont.truetype(font_name_path, 55)    
            except Exception as e:
                print(f"Error loading fonts: {e}")
                font_phone = ImageFont.load_default()
                font_name = ImageFont.load_default()
            
            # Helper para centrar texto
            def draw_centered(text, y, font, color=(0,0,0)):
                try:
                    w = draw.textlength(text, font=font)
                except:
                    w = draw.textbbox((0, 0), text, font=font)[2]
                x = (W - w) // 2
                draw.text((x, y), text, font=font, fill=color)
                return 60 # altura linea aprox (aumentada)
            
            # Dibujar textos debajo del QR
            # Ajustamos el margen superior del texto
            text_y = qr_y + qr_size + 40
            
            # 1) Teléfono (en vez de Evento) - Negrita grande
            draw_centered(telefono, text_y, font_phone)
            text_y += 80 # Espacio extra
            
            # 2) Nombre (Normal grande)
            draw_centered(nombre, text_y, font_name)
            
            out = io.BytesIO()
            bg.save(out, format="PNG")
            return out.getvalue()
            
        except Exception as e:
            print(f"Error usando template: {e}")
            # Fallback al modo normal si falla la imagen
    
    # --- MODO PROG (Fondo blanco) ---
    qr_size = 480
    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)

    # 2) Estilos
    margin = 24
    line_spacing = 10
    try:
        # Load bundled fonts from static folder for Render compatibility
        font_path = os.path.join(app.root_path, 'static', 'arial.ttf')
        font_title = ImageFont.truetype(font_path, 65)
        font_text  = ImageFont.truetype(font_path, 55)
    except Exception as e:
        print(f"Error loading fonts (PROG mode): {e}")
        font_title = ImageFont.load_default()
        font_text  = ImageFont.load_default()

    title = "QR Pass"
    lines = [
        f"Nombre: {nombre}",
        f"Evento: {evento}",
        f"Teléfono: {telefono}",
    ]

    def wrap_line(txt, font, width_px):
        max_chars = max(1, width_px // 12)
        wrapped = []
        for paragraph in txt.split("\n"):
            wrapped.extend(textwrap.wrap(paragraph, width=max_chars))
        return wrapped

    canvas_width = qr_size + margin * 2
    max_text_width = canvas_width - margin * 2

    # Medidas
    dummy = Image.new("RGB", (10, 10))
    ddraw = ImageDraw.Draw(dummy)
    try:
        title_w, title_h = ddraw.textbbox((0, 0), title, font=font_title)[2:]
    except:
        # Fallback para Pillows viejos
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

    # Título centrado
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

    # QR centrado
    qr_x = (canvas_width - qr_size) // 2
    canvas.paste(qr_img, (qr_x, y))
    y += qr_size + margin

    # Textos
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

def make_verification_url(entrada_id: str) -> str:
    path = url_for('verificar', id=entrada_id)  # "/verificar?id=..."
    if EXTERNAL_BASE_URL:
        return EXTERNAL_BASE_URL.rstrip("/") + path
    return (request.host_url.rstrip("/") + path)

def safe_filename(text: str) -> str:
    """Convierte a ASCII, saca tildes y deja solo letras, números, guiones y guiones bajos."""
    if not text:
        return "sin_nombre"
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\-]+", "_", text, flags=re.ASCII)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:60] or "sin_nombre"

# =========================
# Auth
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if verify_session_cookie(request):
        return redirect(request.args.get("next") or url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        try:
            r = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}",
                json={"email": email, "password": password, "returnSecureToken": True},
                timeout=10
            )
            r.raise_for_status()
            id_token = r.json()["idToken"]

            expires_in = timedelta(days=5)
            session_cookie = auth.create_session_cookie(id_token, expires_in=expires_in)

            resp = make_response(redirect(request.args.get("next") or url_for("index")))
            resp.set_cookie(
                "session",
                session_cookie,
                max_age=int(expires_in.total_seconds()),
                httponly=True,
                secure=not DEBUG,  # True en Render (HTTPS)
                samesite="Lax",
            )
            return resp
        except requests.HTTPError as e:
            msg = "Credenciales inválidas."
            try:
                api_msg = e.response.json().get("error", {}).get("message", "")
                if api_msg:
                    msg += f" ({api_msg})"
            except Exception:
                pass
            return render_template("login.html", error=msg, email=email), 401
        except Exception:
            return render_template("login.html", error="Error en el login. Intenta nuevamente."), 500

    return render_template("login.html")

@app.route("/logout")
def logout():
    resp = make_response(redirect(url_for("login")))
    resp.delete_cookie("session")
    return resp

# =========================
# App (rutas)
# =========================
@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/registrar_entrada", methods=["GET", "POST"])
@login_required
def registrar_entrada():
    eventos_docs = db.collection("eventos").stream()
    eventos = [doc.to_dict() for doc in eventos_docs]

    if request.method == "POST":
        evento = request.form["evento"]
        nombre = request.form["nombre"]
        telefono = request.form["telefono"]
        qr_id = str(uuid.uuid4())

        data = {
            "evento": evento,
            "nombre": nombre,
            "telefono": telefono,
            "id": qr_id,
            "estado": "valido",
            "creada_en": datetime.utcnow().isoformat() + "Z",
        }
        db.collection("entradas").document(qr_id).set(data)

        # URL segura de verificación (solo id)
        qr_url = make_verification_url(qr_id)

        # Generar PNG con QR + textos
        png_bytes = build_qr_image_with_text(qr_url, nombre=nombre, evento=evento, telefono=telefono)
        qr_base64 = base64.b64encode(png_bytes).decode("utf-8")

        return render_template(
            "registrar_entrada.html",
            qr_base64=qr_base64,
            qr_id=qr_id,
            evento=evento,
            nombre=nombre,
            telefono=telefono,
            eventos=eventos,
            verify_url=qr_url
        )

    return render_template("registrar_entrada.html", eventos=eventos)

@app.route("/lista")
@login_required
def lista_entradas():
    docs = db.collection("entradas").stream()
    entradas = [doc.to_dict() for doc in docs]
    entradas.sort(key=lambda e: e.get("creada_en", ""), reverse=True)
    conteo_eventos = Counter(
        (e.get("evento") or "(Sin evento)") for e in entradas
    )
    return render_template("lista.html", entradas=entradas, conteo_eventos=conteo_eventos)


@app.route("/eliminar/<entrada_id>", methods=["POST"])
@login_required
def eliminar_entrada(entrada_id):
    db.collection("entradas").document(entrada_id).delete()
    return redirect(url_for("lista_entradas"))

@app.route("/descargar/<id>")
@login_required
def descargar_qr(id):
    snap = db.collection("entradas").document(id).get()
    if not snap.exists:
        return "Entrada no encontrada", 404
    e = snap.to_dict()

    # Datos
    nombre = e.get("nombre", "")
    evento = e.get("evento", "")

    # Genera el PNG
    qr_url = make_verification_url(id)
    png_bytes = build_qr_image_with_text(
        qr_url,
        nombre=nombre,
        evento=evento,
        telefono=e.get("telefono", "")
    )

    # Nombre de archivo: Evento_Nombre.png (sanitizado)
    fname = f"{safe_filename(evento)}_{safe_filename(nombre)}.png"

    buf = io.BytesIO(png_bytes)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name=fname
    )

# ====== EVENTOS ======
@app.route("/registrar_evento", methods=["GET", "POST"])
@login_required
def registrar_evento():
    if request.method == "POST":
        nombre = request.form["nombre"]
        fecha_hora = request.form["fecha_hora"]
        evento_id = str(uuid.uuid4())
        db.collection("eventos").document(evento_id).set({
            "nombre": nombre,
            "fecha_hora": fecha_hora,
            "id": evento_id
        })
        return redirect(url_for("lista_eventos"))
    return render_template("registrar_evento.html")

@app.route('/eventos', endpoint='lista_eventos')
@login_required
def lista_eventos():
    eventos_ref = db.collection('eventos').stream()
    eventos = []
    for doc in eventos_ref:
        data = doc.to_dict() or {}
        data['id'] = data.get('id') or doc.id  # asegurar id usable en template
        eventos.append(data)
    return render_template('eventos.html', eventos=eventos)

@app.route('/eliminar_evento/<evento_id>', methods=['POST'])
@login_required
def eliminar_evento(evento_id):
    try:
        db.collection('eventos').document(evento_id).delete()
        flash("Evento eliminado correctamente.", "success")
    except Exception as e:
        app.logger.exception("Error al eliminar evento")
        flash(f"Error al eliminar evento: {e}", "danger")
    return redirect(url_for('lista_eventos'))

# Alias para compatibilidad con templates viejos
@app.route('/ver_eventos')
@login_required
def ver_eventos():
    return redirect(url_for('lista_eventos'))

# =========================
# Verificación en dos pasos
# =========================
@app.route("/verificar")
@login_required
def verificar():
    entrada_id = request.args.get("id")
    if not entrada_id:
        return render_template("verificacion.html",
                               estado="invalido",
                               nombre=None, evento=None, telefono=None,
                               entrada_id=None)

    snap = db.collection("entradas").document(entrada_id).get()
    if not snap.exists:
        return render_template("verificacion.html",
                               estado="invalido",
                               nombre=None, evento=None, telefono=None,
                               entrada_id=entrada_id)

    e = snap.to_dict()
    return render_template(
        "verificacion.html",
        estado=e.get("estado", "invalido"),
        nombre=e.get("nombre"),
        evento=e.get("evento"),
        telefono=e.get("telefono"),
        entrada_id=entrada_id
    )

@app.route("/verificar/usar", methods=["POST"])
@login_required
def verificar_usar():
    entrada_id = request.form.get("entrada_id")
    if not entrada_id:
        return redirect(url_for("index"))

    doc_ref = db.collection("entradas").document(entrada_id)
    transaction = db.transaction()

    @gcf_firestore.transactional
    def mark_used(tx, ref):
        snap = ref.get(transaction=tx)
        if not snap.exists:
            return {"estado": "invalido", "nombre": None, "evento": None, "telefono": None}
        data = snap.to_dict()
        estado = data.get("estado", "invalido")
        if estado == "valido":
            user = verify_session_cookie(request) or {}
            tx.update(ref, {
                "estado": "usado",
                "usada_en": datetime.utcnow().isoformat() + "Z",
                "usada_por_uid": user.get("uid"),
                "usada_por_email": user.get("email")
            })
            data["estado"] = "usado"
        return {
            "estado": data.get("estado", "invalido"),
            "nombre": data.get("nombre"),
            "evento": data.get("evento"),
            "telefono": data.get("telefono"),
        }

    resultado = mark_used(transaction, doc_ref)
    return render_template("verificacion.html",
                           estado=resultado["estado"],
                           nombre=resultado["nombre"],
                           evento=resultado["evento"],
                           telefono=resultado["telefono"],
                           entrada_id=entrada_id)

# =========================
# Utilidad temporal para depurar rutas (opcional)
# =========================
@app.get("/__map")
def __map():
    return "<pre>" + "\n".join(sorted(str(r) for r in app.url_map.iter_rules())) + "</pre>"

# =========================
# Run (Render / Local)
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=DEBUG)
