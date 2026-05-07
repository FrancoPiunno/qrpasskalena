import os

replacements = {
    "url_for('index')": "url_for('main.index')",
    "url_for('verificar_usar')": "url_for('main.verificar_usar')",
    "url_for('login')": "url_for('auth.login')",
    "url_for('logout')": "url_for('auth.logout')",
    "url_for('registrar_evento')": "url_for('events.registrar_evento')",
    "url_for('lista_eventos')": "url_for('events.lista_eventos')",
    "url_for('eliminar_evento'": "url_for('events.eliminar_evento'",
    "url_for('registrar_entrada')": "url_for('tickets.registrar_entrada')",
    "url_for('lista_entradas')": "url_for('tickets.lista_entradas')",
    "url_for('eliminar_entrada'": "url_for('tickets.eliminar_entrada'",
    "url_for('descargar_lista_pdf')": "url_for('tickets.descargar_lista_pdf')",
    "url_for('descargar_qr'": "url_for('tickets.descargar_qr'"
}

templates_dir = "templates"
for filename in os.listdir(templates_dir):
    if filename.endswith(".html"):
        filepath = os.path.join(templates_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        for old, new in replacements.items():
            content = content.replace(old, new)
            
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
print("Templates actualizados correctamente")
