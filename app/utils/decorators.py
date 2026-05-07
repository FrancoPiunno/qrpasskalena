from functools import wraps
from flask import request, redirect, url_for
from app.firebase import auth

def verify_session_cookie(req):
    session_cookie = req.cookies.get("session")
    if not session_cookie:
        return None
    try:
        decoded = auth.verify_session_cookie(session_cookie, check_revoked=True)
        return decoded
    except Exception:
        return None

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = verify_session_cookie(request)
        if not user:
            return redirect(url_for("auth.login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper
