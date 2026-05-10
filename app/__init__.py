from flask import Flask, request
from app.config import Config

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)

    from app.utils.decorators import verify_session_cookie
    @app.context_processor
    def inject_user():
        return dict(user=verify_session_cookie(request))

    from app.routes.auth import auth_bp
    from app.routes.events import events_bp
    from app.routes.tickets import tickets_bp
    from app.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(main_bp)

    # Forzar recarga de CSS y assets eliminando el caché del navegador
    @app.after_request
    def add_header(response):
        if app.config.get('DEBUG'):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    return app
