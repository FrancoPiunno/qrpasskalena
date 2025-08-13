from flask import Flask, render_template, request, redirect, url_for, send_file, make_response
import os
import io
import base64
import uuid
import qrcode
import requests
from datetime import timedelta, datetime
from functools import wraps

import firebase_admin
from firebase_admin import credentials, firestore, auth
from google.cloud import firestore as gcf_firestore  # para @transactional

from PIL import Image, ImageDraw, ImageFont
import textwrap

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# --- CONFIG ---
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY", "TU_API_KEY_WEB")  # Console > Config > app web
EXTERNAL_BASE_URL = os.environ.get("EXTERNAL_BASE_URL")  # ej: http://192.168.0.23:5000 o https://xxx.ngrok.io

# --- Firebase Admin ---
cred = credentials.Certificate("firebase_key.json")
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
    Genera un PNG con el QR (centro) y los textos abajo (Nombre, Evento, Teléfono).
    Devuelve bytes PNG.
    """
    # 1) QR base
    qr_img = qrcode.make(qr_url).convert("RGB")
    qr_size = 480
    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)

    # 2) Estilos
    margin = 24
    line_spacing = 10
    try:
        font_title = ImageFont.truetype("arial.ttf", 28)
        font_text  = ImageFont.truetype("arial.ttf", 24)
    except:
        font_title = ImageFont.load_default()
        font_text  = ImageFont.load_default()

    title = "QR Pass"
    lines = [
        f"Nombre: {nombre}",
        f"Evento: {evento}",
        f"Teléfono: {telefono}",
    ]

    def wrap_line(txt, font, width_px):
        # envoltorio simple por ancho aprox
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
    # alto del título
    title_w, title_h = ddraw.textbbox((0, 0), title, font=font_title)[2:]

    wrapped_lines, text_block_h = [], 0
    for ln in lines:
        wlines = wrap_line(ln, font_text, max_text_width)
        wrapped_lines.append(wlines)
        for wln in wlines:
            _, h = ddraw.textbbox((0, 0), wln, font=font_text)[2:]
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
        title_len = ddraw.textbbox((0, 0), title, font=font_title)[2]
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
            _, h = ddraw.textbbox((0, 0), wln, font=font_text)[2:]
            y += h + line_spacing

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()

def make_verification_url(entrada_id: str) -> str:
    path = url_for('verificar', id=entrada_id)  # "/verificar?id=..."
    if EXTERNAL_BASE_URL:
        return EXTERNAL_BASE_URL.rstrip("/") + path
    return (request.host_url.rstrip("/") + path)

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
                secure=False if app.debug else True,  # True en prod (HTTPS)
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
    return render_template("lista.html", entradas=entradas)

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

    qr_url = make_verification_url(id)
    png_bytes = build_qr_image_with_text(
        qr_url,
        nombre=e.get("nombre", ""),
        evento=e.get("evento", ""),
        telefono=e.get("telefono", "")
    )

    buf = io.BytesIO(png_bytes)
    buf.seek(0)
    return send_file(buf, mimetype="image/png", as_attachment=True, download_name=f"{id}.png")

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
        return redirect(url_for("ver_eventos"))
    return render_template("registrar_evento.html")

@app.route("/eventos")
@login_required
def ver_eventos():
    docs = db.collection("eventos").stream()
    eventos = [doc.to_dict() for doc in docs]
    return render_template("eventos.html", eventos=eventos)

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
    if not snap.exists:   # <-- ✅ propiedad, sin paréntesis
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
        # devolver siempre los datos para mostrarlos en el template
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
# Run
# =========================
if __name__ == "__main__":
    # Para probar desde el celular en tu LAN, escuchá en 0.0.0.0
    # y seteá EXTERNAL_BASE_URL="http://TU_IP_LOCAL:5000" (o https://xxx.ngrok.io)
    app.run(host="0.0.0.0", port=5000, debug=True)
