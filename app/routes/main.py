from flask import Blueprint, render_template, request, redirect, url_for, current_app
from datetime import datetime

from app.firebase import db
from app.utils.decorators import login_required, verify_session_cookie
from google.cloud import firestore as gcf_firestore

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
@login_required
def index():
    return render_template("index.html")

@main_bp.route("/verificar")
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

@main_bp.route("/verificar/usar", methods=["POST"])
@login_required
def verificar_usar():
    entrada_id = request.form.get("entrada_id")
    if not entrada_id:
        return redirect(url_for("main.index"))

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

@main_bp.get("/__map")
def __map():
    return "<pre>" + "\n".join(sorted(str(r) for r in current_app.url_map.iter_rules())) + "</pre>"
