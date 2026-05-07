import os
import json
import base64
import firebase_admin
from firebase_admin import credentials, firestore, auth

def load_firebase_credentials():
    env_key = os.environ.get("FIREBASE_KEY_JSON")
    if env_key:
        try:
            txt = env_key if env_key.strip().startswith("{") else base64.b64decode(env_key).decode("utf-8")
            data = json.loads(txt)
            return credentials.Certificate(data)
        except Exception as e:
            print("WARN: No pude parsear FIREBASE_KEY_JSON, usando firebase_key.json. Error:", e)
    return credentials.Certificate("firebase_key.json")

def init_firebase():
    if not firebase_admin._apps:
        cred = load_firebase_credentials()
        firebase_admin.initialize_app(cred)

init_firebase()
db = firestore.client()
