"""Local AV prototype. All authoritative geometry is calculated in Python."""
import json
import sqlite3
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_file
from engine import calculate

BASE = Path(__file__).resolve().parent
app = Flask(__name__)
# Keep specification rows in their supplied datasheet order.
app.json.sort_keys = False
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


@app.after_request
def refresh_app_code(response):
    # Local installations are updated in place; do not retain an older UI bundle.
    if request.path == '/' or request.path.endswith('.js'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.after_request
def refresh_app_code(response):
    # Local installations are updated in place; refresh the UI bundle.
    if request.path == '/' or request.path.endswith('.js'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/catalogue")
def catalogue():
    response = jsonify(json.loads((BASE / "catalogue.json").read_text(encoding="utf-8")))
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get("/api/controllers")
def controllers():
    response = jsonify(json.loads((BASE / "controllers.json").read_text(encoding="utf-8")))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/api/calculate")
def compute():
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object"), 400
    try:
        return jsonify(calculate(data))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)), 400


def database():
    con = sqlite3.connect(BASE / "projects.db")
    con.execute("CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP)")
    return con


@app.get("/api/projects")
def projects():
    with database() as con:
        records = con.execute("SELECT id,name,created FROM projects ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(id=r[0], name=r[1], created=r[2]) for r in records])


@app.get("/api/projects/<int:project_id>")
def project(project_id):
    with database() as con:
        row = con.execute("SELECT payload FROM projects WHERE id=?", (project_id,)).fetchone()
    return (jsonify(json.loads(row[0])), 200) if row else (jsonify(error="Project not found"), 404)


@app.post("/api/projects")
def save():
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object"), 400
    name = str(data.get("name", "Untitled project")).strip()[:120] or "Untitled project"
    try:
        calculate(data)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)), 400
    with database() as con:
        cur = con.execute("INSERT INTO projects(name,payload) VALUES (?,?)", (name, json.dumps(data)))
        project_id = cur.lastrowid
    return jsonify(id=project_id, name=name), 201


@app.post("/api/quotation")
def quotation():
    from quotation import build_quotation
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object"), 400
    details = data.get("quotation")
    if not isinstance(details, dict):
        return jsonify(error="Enter client name, sales person and contact information before downloading the quotation."), 400
    required = {"client": "client name", "salesperson": "sales person", "contact": "contact information"}
    missing = [label for key, label in required.items()
               if not isinstance(details.get(key), str) or not details[key].strip()]
    if missing:
        return jsonify(error="Enter " + ", ".join(missing) + " before downloading the quotation."), 400
    for key in required:
        details[key] = details[key].strip()
    try:
        output = build_quotation(data, BASE)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)), 400
    return send_file(output, as_attachment=True, download_name="PROMARK-LED-STUDIO-Quotation.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
