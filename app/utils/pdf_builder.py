import os
from fpdf import FPDF
from flask import make_response, current_app
from datetime import datetime
from app.firebase import db

def descargar_lista_pdf_logic():
    docs = db.collection("entradas").stream()
    entradas = [doc.to_dict() for doc in docs]
    entradas.sort(key=lambda e: (e.get("evento", "").lower(), e.get("numero", 0)))

    pdf = FPDF()
    pdf.add_page()
    
    font_path = os.path.join(current_app.static_folder, 'arial.ttf')
    if os.path.exists(font_path):
        pass
    
    pdf.set_font("Arial", size=12)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Lista de Entradas Generadas", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(20, 10, "N°", 1, align="C")
    pdf.cell(50, 10, "Evento", 1)
    pdf.cell(65, 10, "Nombre", 1)
    pdf.cell(55, 10, "Teléfono".encode('latin-1').decode('latin-1'), 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=12)
    for ent in entradas:
        numero = str(ent.get("numero") or "")
        evento = ent.get("evento", "") or ""
        nombre = ent.get("nombre", "") or ""
        telefono = ent.get("telefono", "") or ""
        
        def clean(txt):
            return txt.encode('latin-1', 'replace').decode('latin-1')

        pdf.cell(20, 10, clean(numero), 1, align="C")
        pdf.cell(50, 10, clean(evento)[:20], 1)
        pdf.cell(65, 10, clean(nombre)[:25], 1)
        pdf.cell(55, 10, clean(telefono), 1)
        pdf.ln()

    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers['Content-Type'] = 'application/pdf'
    filename = f"lista_entradas_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response
