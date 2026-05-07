from flask import Blueprint, request, redirect, url_for, render_template, flash, current_app
import uuid
from app.firebase import db
from app.utils.decorators import login_required

events_bp = Blueprint('events', __name__)

@events_bp.route("/registrar_evento", methods=["GET", "POST"])
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
        return redirect(url_for("events.lista_eventos"))
    return render_template("registrar_evento.html")

@events_bp.route('/eventos', endpoint='lista_eventos')
@login_required
def lista_eventos():
    eventos_ref = db.collection('eventos').stream()
    eventos = []
    for doc in eventos_ref:
        data = doc.to_dict() or {}
        data['id'] = data.get('id') or doc.id
        eventos.append(data)
    return render_template('eventos.html', eventos=eventos)

@events_bp.route('/eliminar_evento/<evento_id>', methods=['POST'])
@login_required
def eliminar_evento(evento_id):
    try:
        db.collection('eventos').document(evento_id).delete()
        flash("Evento eliminado correctamente.", "success")
    except Exception as e:
        current_app.logger.exception("Error al eliminar evento")
        flash(f"Error al eliminar evento: {e}", "danger")
    return redirect(url_for('events.lista_eventos'))

@events_bp.route('/ver_eventos')
@login_required
def ver_eventos():
    return redirect(url_for('events.lista_eventos'))
