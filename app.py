from flask import Flask, render_template, request, send_file, url_for
import qrcode
import uuid
from io import BytesIO
import base64
from PIL import Image, ImageDraw, ImageFont
import firebase_admin
from firebase_admin import credentials, firestore
import os

# Inicializar Firebase
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    qr_base64 = None
    nombre_evento = ""
    nombre_persona = ""
    telefono = ""
    qr_id = None

    if request.method == 'POST':
        nombre_evento = request.form['evento']
        nombre_persona = request.form['nombre']
        telefono = request.form['telefono']
        qr_id = str(uuid.uuid4())

        qr_link = f"http://localhost:5000/entrada?id={qr_id}"
        qr_img = qrcode.make(qr_link).convert('RGB')

        qr_width, qr_height = qr_img.size
        extra_height = 100
        combined_img = Image.new('RGB', (qr_width, qr_height + extra_height), 'white')
        combined_img.paste(qr_img, (0, 0))

        draw = ImageDraw.Draw(combined_img)
        text = f"{nombre_evento}\n{nombre_persona}\n{telefono}"

        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (qr_width - text_width) // 2
        text_y = qr_height + 10
        draw.multiline_text((text_x, text_y), text, fill='black', font=font, align='center')

        # Convertir a base64 para mostrar en HTML
        img_io = BytesIO()
        combined_img.save(img_io, format='PNG')
        img_io.seek(0)
        qr_base64 = base64.b64encode(img_io.getvalue()).decode()

        # Guardar datos en Firebase
        db.collection('entradas').document(qr_id).set({
            'evento': nombre_evento,
            'nombre': nombre_persona,
            'telefono': telefono,
            'estado': 'valido'
        })

    return render_template(
        'index.html',
        qr_base64=qr_base64,
        evento=nombre_evento,
        nombre=nombre_persona,
        telefono=telefono,
        qr_id=qr_id
    )

@app.route('/entrada')
def verificar_qr():
    qr_id = request.args.get('id')
    estado = "invalido"
    nombre = ""

    if qr_id:
        doc = db.collection('entradas').document(qr_id).get()
        if doc.exists:
            data = doc.to_dict()
            nombre = data.get('nombre', '')
            estado_actual = data.get('estado')

            if estado_actual == 'valido':
                estado = 'valido'
                db.collection('entradas').document(qr_id).update({'estado': 'usado'})
            elif estado_actual == 'usado':
                estado = 'usado'

    return render_template("verificacion.html", estado=estado, nombre=nombre)

@app.route('/descargar')
def descargar_qr():
    qr_id = request.args.get('id')
    doc = db.collection('entradas').document(qr_id).get()
    if not doc.exists:
        return "❌ QR no encontrado", 404

    data = doc.to_dict()
    qr_link = f"http://localhost:5000/entrada?id={qr_id}"

    qr_img = qrcode.make(qr_link).convert('RGB')

    qr_width, qr_height = qr_img.size
    extra_height = 100
    combined_img = Image.new('RGB', (qr_width, qr_height + extra_height), 'white')
    combined_img.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(combined_img)
    text = f"{data['evento']}\n{data['nombre']}\n{data['telefono']}"
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = (qr_width - text_width) // 2
    text_y = qr_height + 10
    draw.multiline_text((text_x, text_y), text, fill='black', font=font)

    img_io = BytesIO()
    combined_img.save(img_io, format='PNG')
    img_io.seek(0)

    def limpiar(texto):
        return (
            texto.lower()
            .replace(" ", "_")
            .replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u")
            .replace("ñ", "n")
        )

    nombre_archivo = f"{limpiar(data['evento'])}_{limpiar(data['nombre'])}.png"

    return send_file(
        img_io,
        mimetype='image/png',
        as_attachment=True,
        download_name=nombre_archivo
    )

if __name__ == '__main__':
    app.run(debug=True)
