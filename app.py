from flask import Flask, render_template, request, redirect, url_for, send_file, make_response
import os
import io
import base64
import uuid
import qrcode
import requests
from datetime import timedelta
from functools import wraps

import firebase_admin
from firebase_admin import credentials, firestore, auth

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

# --- CONFIG ---
FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY", "TU_API_KEY_WEB")  # de tu app web (Console > Config)

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
        return decoded
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
    # Para poder usar {% if user %} en todos los templates
    return dict(user=verify_session_cookie(request))

# =========================
# Auth
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    # Si ya está logueado, redirige
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
                secure=False if app.debug else True,
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
# App
# =========================

# Menú principal (solo enlaces)
@app.route("/")
@login_required
def index():
    # Tu index.html ahora es un menú con <a> a registrar_entrada, lista, eventos, etc.
    return render_template("index.html")

# Registrar ENTRADA (antes estaba en '/')
@app.route("/registrar_entrada", methods=["GET", "POST"])
@login_required
def registrar_entrada():
    # Cargar eventos para el <select>
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
        }
        db.collection("entradas").document(qr_id).set(data)

        # Generar QR (solo el ID; tu verificación lo usará)
        qr_img = qrcode.make(qr_id)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return render_template(
            "registrar_entrada.html",
            qr_base64=qr_base64,
            qr_id=qr_id,
            evento=evento,
            nombre=nombre,
            telefono=telefono,
            eventos=eventos
        )

    # GET
    return render_template("registrar_entrada.html", eventos=eventos)

# Lista de entradas
@app.route("/lista")
@login_required
def lista_entradas():
    docs = db.collection("entradas").stream()
    entradas = [doc.to_dict() for doc in docs]
    return render_template("lista.html", entradas=entradas)

# Eliminar entrada
@app.route("/eliminar/<entrada_id>", methods=["POST"])
@login_required
def eliminar_entrada(entrada_id):
    db.collection("entradas").document(entrada_id).delete()
    return redirect(url_for("lista_entradas"))

# Descargar QR
@app.route("/descargar/<id>")
@login_required
def descargar_qr(id):
    qr_img = qrcode.make(id)
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png", as_attachment=True, download_name=f"{id}.png")

# Registrar EVENTO
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

# Ver eventos
@app.route("/eventos")
@login_required
def ver_eventos():
    docs = db.collection("eventos").stream()
    eventos = [doc.to_dict() for doc in docs]
    return render_template("eventos.html", eventos=eventos)

if __name__ == "__main__":
    # En prod: usar gunicorn/uwsgi y HTTPS (para cookie secure)
    app.run(debug=True)
