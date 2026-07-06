from flask import Blueprint, request, render_template, redirect, url_for, send_file
import uuid
import base64
import io
from datetime import datetime
from collections import Counter
from google.cloud import firestore

from app.firebase import db
from app.utils.decorators import login_required
from app.utils.helpers import make_verification_url, safe_filename
from app.utils.qr_generator import build_qr_image_with_text
from app.utils.pdf_builder import descargar_lista_pdf_logic

tickets_bp = Blueprint('tickets', __name__)

def get_next_ticket_number(evento):
    entradas_ref = db.collection("entradas")
    query = entradas_ref.where("evento", "==", evento).order_by("numero", direction=firestore.Query.DESCENDING).limit(1)
    results = list(query.stream())
    if results:
        max_num = results[0].to_dict().get("numero", 0)
        return max_num + 1
    else:
        all_event_docs = list(entradas_ref.where("evento", "==", evento).stream())
        if all_event_docs:
            nums = [doc.to_dict().get("numero") for doc in all_event_docs if "numero" in doc.to_dict()]
            if nums:
                return max(nums) + 1
            return len(all_event_docs) + 1
        return 1

@tickets_bp.route("/registrar_entrada", methods=["GET", "POST"])
@login_required
def registrar_entrada():
    eventos_docs = db.collection("eventos").stream()
    eventos = [doc.to_dict() for doc in eventos_docs]

    if request.method == "POST":
        evento = request.form["evento"]
        nombre = request.form["nombre"]
        telefono = request.form["telefono"]
        qr_id = str(uuid.uuid4())

        numero = get_next_ticket_number(evento)

        data = {
            "evento": evento,
            "nombre": nombre,
            "telefono": telefono,
            "id": qr_id,
            "estado": "valido",
            "creada_en": datetime.utcnow().isoformat() + "Z",
            "numero": numero,
        }
        db.collection("entradas").document(qr_id).set(data)

        qr_url = make_verification_url(qr_id)
        png_bytes = build_qr_image_with_text(qr_url, nombre=nombre, evento=evento, telefono=telefono, numero=numero)
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

@tickets_bp.route("/lista")
@login_required
def lista_entradas():
    docs = db.collection("entradas").stream()
    entradas = [doc.to_dict() for doc in docs]
    entradas.sort(key=lambda e: (e.get("evento", "").lower(), e.get("numero", 0)))
    conteo_eventos = Counter(
        (e.get("evento") or "(Sin evento)") for e in entradas
    )
    return render_template("lista.html", entradas=entradas, conteo_eventos=conteo_eventos)

@tickets_bp.route("/asignar_numeros", methods=["POST"])
@login_required
def asignar_numeros():
    docs = db.collection("entradas").stream()
    entradas = []
    for doc in docs:
        d = doc.to_dict()
        d["_doc_id"] = doc.id
        entradas.append(d)
        
    by_event = {}
    for e in entradas:
        ev = e.get("evento", "(Sin evento)")
        if ev not in by_event:
            by_event[ev] = []
        by_event[ev].append(e)
        
    for ev, ev_entradas in by_event.items():
        ev_entradas.sort(key=lambda x: x.get("creada_en", ""))
        for index, e in enumerate(ev_entradas):
            doc_id = e["_doc_id"]
            num = index + 1
            db.collection("entradas").document(doc_id).update({"numero": num})
            
    return redirect(url_for("tickets.lista_entradas"))

@tickets_bp.route("/eliminar/<entrada_id>", methods=["POST"])
@login_required
def eliminar_entrada(entrada_id):
    db.collection("entradas").document(entrada_id).delete()
    return redirect(url_for("tickets.lista_entradas"))

@tickets_bp.route("/descargar_lista_pdf")
@login_required
def descargar_lista_pdf():
    return descargar_lista_pdf_logic()

@tickets_bp.route("/descargar/<id>")
@login_required
def descargar_qr(id):
    snap = db.collection("entradas").document(id).get()
    if not snap.exists:
        return "Entrada no encontrada", 404
    e = snap.to_dict()

    nombre = e.get("nombre", "")
    evento = e.get("evento", "")
    numero = e.get("numero")

    qr_url = make_verification_url(id)
    png_bytes = build_qr_image_with_text(
        qr_url,
        nombre=nombre,
        evento=evento,
        telefono=e.get("telefono", ""),
        numero=numero
    )

    fname = f"{safe_filename(evento)}_{safe_filename(nombre)}.png"

    buf = io.BytesIO(png_bytes)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="image/png",
        as_attachment=True,
        download_name=fname
    )
