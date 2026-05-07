import unicodedata
import re
from flask import url_for, request
from app.config import Config

def make_verification_url(entrada_id: str) -> str:
    path = url_for('main.verificar', id=entrada_id)
    if Config.EXTERNAL_BASE_URL:
        return Config.EXTERNAL_BASE_URL.rstrip("/") + path
    return (request.host_url.rstrip("/") + path)

def safe_filename(text: str) -> str:
    if not text:
        return "sin_nombre"
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\-]+", "_", text, flags=re.ASCII)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:60] or "sin_nombre"
