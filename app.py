import os
import logging
from functools import wraps
from typing import Any, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("devhub")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]   # service_role (só no backend!)
API_TOKEN    = os.environ["API_TOKEN"]              # token de escrita da equipe
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")  # ex: https://seu-hub.vercel.app

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE = "projects"

app = Flask(__name__)
CORS(app, origins="*" if ALLOWED_ORIGIN == "*" else [ALLOWED_ORIGIN])


def require_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if token != API_TOKEN:
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


def validate(data: Any) -> tuple[Optional[dict], Optional[str]]:
    if not isinstance(data, dict):
        return None, "corpo inválido"
    name = (data.get("name") or "").strip()
    if not name:
        return None, "name é obrigatório"
    raw_tags = data.get("tags", [])
    tags = [t.strip() for t in raw_tags if isinstance(t, str) and t.strip()] if isinstance(raw_tags, list) else []
    return {
        "name": name,
        "summary": (data.get("summary") or "").strip(),
        "owner": (data.get("owner") or "").strip(),
        "tags": tags,
        "repo_url": (data.get("repo_url") or "").strip(),
        "doc_md": data.get("doc_md") or "",
    }, None


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/projects")
def list_projects():
    try:
        res = supabase.table(TABLE).select("*").order("created_at", desc=True).execute()
        return jsonify(res.data)
    except Exception:
        log.exception("list failed")
        return jsonify({"error": "erro interno"}), 500


@app.post("/projects")
@require_token
def create_project():
    clean, err = validate(request.get_json(silent=True) or {})
    if err:
        return jsonify({"error": err}), 400
    try:
        res = supabase.table(TABLE).insert(clean).execute()
        log.info("criado: %s", clean["name"])
        return jsonify(res.data[0]), 201
    except Exception:
        log.exception("create failed")
        return jsonify({"error": "erro interno"}), 500


@app.put("/projects/<pid>")
@require_token
def update_project(pid: str):
    clean, err = validate(request.get_json(silent=True) or {})
    if err:
        return jsonify({"error": err}), 400
    try:
        res = supabase.table(TABLE).update(clean).eq("id", pid).execute()
        if not res.data:
            return jsonify({"error": "não encontrado"}), 404
        return jsonify(res.data[0])
    except Exception:
        log.exception("update failed")
        return jsonify({"error": "erro interno"}), 500


@app.delete("/projects/<pid>")
@require_token
def delete_project(pid: str):
    try:
        supabase.table(TABLE).delete().eq("id", pid).execute()
        return jsonify({"deleted": True})
    except Exception:
        log.exception("delete failed")
        return jsonify({"error": "erro interno"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))