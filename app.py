from flask import Flask, render_template, request, redirect, url_for, send_file
import firebase_admin
from firebase_admin import credentials, firestore
import qrcode
import io
import base64
import uuid

app = Flask(__name__)

# Inicializar Firestore con tu clave
cred = credentials.Certificate("firebase_key.json")  # Archivo JSON de tu clave de Firebase
firebase_admin.initialize_app(cred)
db = firestore.client()

# Página principal con formulario para generar QR
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        evento = request.form['evento']
        nombre = request.form['nombre']
        telefono = request.form['telefono']
        qr_id = str(uuid.uuid4())

        data = {
            "evento": evento,
            "nombre": nombre,
            "telefono": telefono,
            "id": qr_id,
            "estado": "valido"
        }
        db.collection("entradas").document(qr_id).set(data)

        # Crear QR
        qr_img = qrcode.make(qr_id)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Recargar eventos
        eventos_docs = db.collection("eventos").stream()
        eventos = [doc.to_dict() for doc in eventos_docs]

        return render_template("index.html", qr_base64=qr_base64, qr_id=qr_id,
                               evento=evento, nombre=nombre, telefono=telefono,
                               eventos=eventos)

    # Método GET → traer eventos
    eventos_docs = db.collection("eventos").stream()
    eventos = [doc.to_dict() for doc in eventos_docs]
    return render_template("index.html", eventos=eventos)

# Lista de entradas
@app.route('/lista')
def lista_entradas():
    docs = db.collection("entradas").stream()
    entradas = [doc.to_dict() for doc in docs]
    return render_template("lista.html", entradas=entradas)

# Eliminar entrada
@app.route('/eliminar/<entrada_id>', methods=['POST'])
def eliminar_entrada(entrada_id):
    db.collection("entradas").document(entrada_id).delete()
    return redirect(url_for('lista_entradas'))

# Descargar QR
@app.route('/descargar/<id>')
def descargar_qr(id):
    qr_img = qrcode.make(id)
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png", as_attachment=True, download_name=f"{id}.png")

# Registrar evento
@app.route('/registrar_evento', methods=['GET', 'POST'])
def registrar_evento():
    if request.method == 'POST':
        nombre = request.form['nombre']
        fecha_hora = request.form['fecha_hora']

        evento_id = str(uuid.uuid4())
        data = {
            "nombre": nombre,
            "fecha_hora": fecha_hora,
            "id": evento_id
        }
        db.collection("eventos").document(evento_id).set(data)
        return redirect(url_for('ver_eventos'))

    return render_template("registrar_evento.html")

# Ver eventos
@app.route('/eventos')
def ver_eventos():
    docs = db.collection("eventos").stream()
    eventos = [doc.to_dict() for doc in docs]
    return render_template("eventos.html", eventos=eventos)

if __name__ == '__main__':
    app.run(debug=True)
