import os

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"
    FIREBASE_WEB_API_KEY = os.environ.get("FIREBASE_WEB_API_KEY", "TU_API_KEY_WEB")
    EXTERNAL_BASE_URL = os.environ.get("EXTERNAL_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    
    # Optimizaciones para Desarrollo en Tiempo Real
    TEMPLATES_AUTO_RELOAD = True
    SEND_FILE_MAX_AGE_DEFAULT = 0
