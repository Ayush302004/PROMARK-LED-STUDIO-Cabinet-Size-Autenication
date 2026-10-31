"""LED Wall Designer with MongoDB Authentication."""
import json
import re
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_file, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

from engine import calculate
from config import Config
from auth.routes import auth_bp
from auth.middleware import require_auth, require_admin
from auth.models import initialize_database, Project, User, Session, get_db

BASE = Path(__file__).resolve().parent
app = Flask(__name__)

# Load configuration
Config.validate()
app.config.from_object(Config)
app.json.sort_keys = False
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

# Initialize rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per minute"],
    storage_uri="memory://"
)

# Security headers (production only)
if Config.FLASK_ENV == 'production' and Config.SESSION_COOKIE_SECURE:
    Talisman(app, force_https=True)

# Register blueprints
app.register_blueprint(auth_bp)

# Rate limit auth endpoints (after blueprint registration)
# Access view functions through the app's view_functions dict with blueprint prefix
limiter.limit(f"{Config.RATE_LIMIT_LOGIN} per minute")(app.view_functions['auth.login'])
limiter.limit(f"{Config.RATE_LIMIT_REGISTER} per minute")(app.view_functions['auth.register'])
limiter.limit(f"{Config.RATE_LIMIT_REFRESH} per minute")(app.view_functions['auth.refresh'])

# Initialize MongoDB
initialize_database()


@app.after_request
def refresh_app_code(response):
    if request.path == '/' or request.path.endswith('.js'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.before_request
def cleanup_sessions():
    """Cleanup expired sessions periodically."""
    import random
    if random.random() < 0.01:
        Session.cleanup_expired()


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/login")
def login_page():
    return render_template("login.html")


@app.get("/admin")
@require_admin
def admin_dashboard():
    return render_template("admin.html")


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


# ==================== PROJECT ENDPOINTS ====================

@app.get("/api/projects")
@require_auth
def get_projects():
    """Get current user's projects with pagination."""
    try:
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = max(int(request.args.get('offset', 0)), 0)
    except ValueError:
        limit, offset = 100, 0
    
    projects, total = Project.get_by_user(g.user_id, limit, offset)
    
    # Format dates properly for frontend
    for project in projects:
        if 'created_at' in project:
            project['created_at'] = project['created_at'].strftime('%Y-%m-%d %H:%M')
        if 'updated_at' in project:
            project['updated_at'] = project['updated_at'].strftime('%Y-%m-%d %H:%M')
    
    return jsonify({
        'projects': projects,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.get("/api/projects/<project_id>")
@require_auth
def get_project(project_id):
    """Get specific project (ownership verified)."""
    project = Project.get_by_id(project_id, g.user_id)
    
    if not project:
        return jsonify(error="Project not found"), 404
    
    # Return the full payload directly (not nested)
    return jsonify(project['payload'])


@app.post("/api/projects")
@require_auth
def create_project():
    """Create new project."""
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object"), 400
    
    name = str(data.get("name", "Untitled project")).strip()[:120] or "Untitled project"
    
    # Validate design
    try:
        calculate(data)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)), 400
    
    # Create project
    project_id = Project.create(g.user_id, name, data)
    
    return jsonify(id=project_id, name=name), 201


@app.put("/api/projects/<project_id>")
@require_auth
def update_project(project_id):
    """Update project (ownership verified)."""
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object"), 400
    
    name = str(data.get("name", "Untitled project")).strip()[:120] or "Untitled project"
    
    # Validate design
    try:
        calculate(data)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)), 400
    
    # Update project
    success = Project.update(project_id, g.user_id, name, data)
    
    if not success:
        return jsonify(error="Project not found or access denied"), 404
    
    return jsonify(id=project_id, name=name)


@app.delete("/api/projects/<project_id>")
@require_auth
def delete_project(project_id):
    """Delete project (ownership verified)."""
    success = Project.delete(project_id, g.user_id)
    
    if not success:
        return jsonify(error="Project not found or access denied"), 404
    
    return jsonify(message="Project deleted successfully")


# ==================== ADMIN ENDPOINTS ====================

@app.get("/api/admin/dashboard")
@require_admin
def admin_dashboard_data():
    """Get admin dashboard statistics."""
    db = get_db()
    
    stats = {
        'total_users': User.count(),
        'total_projects': Project.count()
    }
    
    # Recent projects
    projects, _ = Project.get_all_with_owners(limit=10)
    
    return jsonify({
        'stats': stats,
        'recent_projects': projects
    })


@app.get("/api/admin/users")
@require_admin
def admin_get_users():
    """Get all users with project counts."""
    try:
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = max(int(request.args.get('offset', 0)), 0)
    except ValueError:
        limit, offset = 100, 0
    
    users = User.get_all(limit, offset)
    total = User.count()
    
    return jsonify({
        'users': users,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.get("/api/admin/projects")
@require_admin
def admin_get_projects():
    """Get all projects with owner information."""
    try:
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = max(int(request.args.get('offset', 0)), 0)
        user_id = request.args.get('user_id')
    except ValueError:
        limit, offset, user_id = 100, 0, None
    
    projects, total = Project.get_all_with_owners(limit, offset, user_id)
    
    return jsonify({
        'projects': projects,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@app.get("/api/admin/projects/<project_id>")
@require_admin
def admin_get_project(project_id):
    """Get any project by ID (admin access)."""
    project = Project.get_by_id(project_id)
    
    if not project:
        return jsonify(error="Project not found"), 404
    
    return jsonify(project)


def quotation_filename(data):
    details = data.get("quotation") or {}
    salesperson = re.sub(r'[\\/:*?"<>|]+', '-', str(details.get("salesperson", "Sales Person")).strip())
    salesperson = re.sub(r'\s+', ' ', salesperson).strip(' .-') or "Sales Person"

    product = data.get("product") or {}
    pitch = product.get("model_pitch_mm", product.get("pitch_mm"))
    pitch_text = f"{float(pitch):g}mm" if pitch not in (None, "") else "LED"
    technology = str(product.get("technology") or "SMD").upper()
    environment = str(product.get("environment") or "Indoor").strip().capitalize()

    calculated = calculate(data)
    unit = data.get("unit", "m")

    if data.get("mode") == "dimensions":
        width_value = data.get("screen_width")
        height_value = data.get("screen_height")
    else:
        meter_width = calculated.get("width_m") if isinstance(calculated, dict) else 0
        meter_height = calculated.get("height_m") if isinstance(calculated, dict) else 0
        try:
            width_value = float(meter_width) / 0.3048 if unit == "ft" else float(meter_width)
            height_value = float(meter_height) / 0.3048 if unit == "ft" else float(meter_height)
        except (TypeError, ValueError):
            width_value = height_value = 0

    try:
        width_value = float(width_value)
        height_value = float(height_value)
    except (TypeError, ValueError):
        width_value = height_value = 0

    size_text = f"{width_value:.3f}W x {height_value:.3f}H {unit}"
    download_date = datetime.now().strftime("%d-%m-%Y")
    return f"Quotation of {pitch_text} {technology} {environment} ({size_text}) {download_date} ({salesperson}).xlsx"


@app.post("/api/quotation")
@require_auth
def quotation():
    """Generate quotation Excel file."""
    from quotation import build_quotation
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify(error="Expected a JSON object"), 400
    details = data.get("quotation")
    if not isinstance(details, dict):
        return jsonify(error="Enter client name, sales person and contact information"), 400
    required = {"client": "client name", "salesperson": "sales person", "contact": "contact information"}
    missing = [label for key, label in required.items()
               if not isinstance(details.get(key), str) or not details[key].strip()]
    if missing:
        return jsonify(error="Enter " + ", ".join(missing)), 400
    for key in required:
        details[key] = details[key].strip()
    try:
        output_format = request.args.get("format", "xlsx").lower()
        if output_format == "pdf":
            from quotation import build_quotation_pdf
            output = build_quotation_pdf(data, BASE)
            filename = quotation_filename(data).rsplit('.', 1)[0] + '.pdf'
            mimetype = 'application/pdf'
        else:
            output = build_quotation(data, BASE)
            filename = quotation_filename(data)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    except (ValueError, TypeError, KeyError, ImportError) as exc:
        return jsonify(error=str(exc)), 400
    return send_file(output, as_attachment=True, download_name=filename, mimetype=mimetype)


@app.post("/api/quotation/from-excel")
@require_auth
def quotation_from_excel():
    """Convert an edited Excel quotation worksheet into a PDF."""
    uploaded = request.files.get("quotation")
    if uploaded is None:
        return jsonify(error="Select an edited Excel quotation file"), 400
    filename = uploaded.filename or "Quotation-edited.xlsx"
    if not filename.lower().endswith(".xlsx"):
        return jsonify(error="Only .xlsx Excel quotation files are supported"), 400
    try:
        from quotation import build_pdf_from_excel
        output = build_pdf_from_excel(uploaded.stream, Path(filename).stem)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:
        return jsonify(error=f"Unable to convert edited Excel: {exc}"), 400
    pdf_name = re.sub(r'[\\/:*?"<>|]+', '-', Path(filename).stem).strip(' .-') or 'Quotation-edited'
    pdf_name = pdf_name.replace('.xlsx', '') + '.pdf'
    return send_file(output, as_attachment=True, download_name=pdf_name, mimetype='application/pdf')


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

