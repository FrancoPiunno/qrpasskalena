from flask import Blueprint, request, redirect, url_for, render_template, make_response
import requests
from datetime import timedelta
from app.firebase import auth
from app.config import Config
from app.utils.decorators import verify_session_cookie

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if verify_session_cookie(request):
        return redirect(request.args.get("next") or url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        try:
            r = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={Config.FIREBASE_WEB_API_KEY}",
                json={"email": email, "password": password, "returnSecureToken": True},
                timeout=10
            )
            r.raise_for_status()
            id_token = r.json()["idToken"]

            expires_in = timedelta(days=5)
            session_cookie = auth.create_session_cookie(id_token, expires_in=expires_in)

            resp = make_response(redirect(request.args.get("next") or url_for("main.index")))
            resp.set_cookie(
                "session",
                session_cookie,
                max_age=int(expires_in.total_seconds()),
                httponly=True,
                secure=not Config.DEBUG,
                samesite="Lax",
            )
            return resp
        except requests.HTTPError as e:
            msg = "Credenciales inválidas."
            try:
                api_msg = e.response.json().get("error", {}).get("message", "")
                if api_msg:
                    msg += f" ({api_msg})"
            except Exception:
                pass
            return render_template("login.html", error=msg, email=email), 401
        except Exception:
            return render_template("login.html", error="Error en el login. Intenta nuevamente."), 500

    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    resp = make_response(redirect(url_for("auth.login")))
    resp.delete_cookie("session")
    return resp
