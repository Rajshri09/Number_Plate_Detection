"""
ANPR System — Rebuilt Flask App
Uses proper Jinja2 template files. All detection/OCR/DB logic from originals.
"""

from flask import (Flask, request, jsonify, render_template,
                   session, redirect, url_for, Response)
import cv2, numpy as np, base64, tempfile, os, csv, io
from PIL import Image
from functools import wraps

from detector import detect_plates
from ocr      import get_text
from database import (init_db, save_plate, get_all, delete_all,
                      delete_by_id, add_plate_manual, get_stats,
                      register_user, login_user, get_user_by_id)

app = Flask(__name__)
app.secret_key = "anpr-super-secret-2024"
init_db()

# ── Auth decorator ─────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════════════════════════
# PUBLIC PAGES
# ══════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    """Landing / About hero page (replaces old /about)."""
    return render_template("index.html", active="home")

# ══════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    error = ""
    if request.method == "POST":
        user = login_user(request.form["username"], request.form["password"])
        if user:
            session["user_id"]  = user[0]
            session["username"] = user[1]
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."
    return render_template("login.html", active="login", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    error = ""
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        email    = request.form.get("email", "").strip()
        if len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif not register_user(username, password, email):
            error = "Username already taken. Try another."
        else:
            return redirect(url_for("login"))
    return render_template("register.html", active="register", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ══════════════════════════════════════════════════════════════════════════
# PROTECTED PAGES
# ══════════════════════════════════════════════════════════════════════════

@app.route("/detect")
@login_required
def detect():
    """Detection page — now requires login."""
    return render_template("detect.html", active="detect")

@app.route("/dashboard")
@login_required
def dashboard():
    uid   = session["user_id"]
    uname = session["username"]
    stats = get_stats(uid)
    user  = get_user_by_id(uid)
    return render_template("dashboard.html", active="dashboard",
                           uname=uname, stats=stats, user=user)

@app.route("/records")
@login_required
def records_page():
    uid  = session["user_id"]
    rows = get_all(uid)
    return render_template("records.html", active="records",
                           rows=rows, count=len(rows))

# ══════════════════════════════════════════════════════════════════════════
# DETECTION API
# ══════════════════════════════════════════════════════════════════════════

def _process_frame(frame, source_name):
    annotated, crops = detect_plates(frame)
    found = []
    for crop in crops:
        results = get_text(crop)
        for plate, conf in results:
            # Logic kept: uses current session user_id
            save_plate(plate, source_name, session.get("user_id"))
            found.append({"plate": plate, "conf": conf})
    return annotated, found

@app.route("/detect/image", methods=["POST"])
@login_required
def detect_image():
    img   = Image.open(request.files["file"].stream).convert("RGB")
    frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    annotated, found = _process_frame(frame, "image")
    _, buf = cv2.imencode(".jpg", annotated)
    return jsonify({"plates": found, "annotated": base64.b64encode(buf).decode()})

@app.route("/detect/video", methods=["POST"])
@login_required
def detect_video():
    f      = request.files["file"]
    suffix = os.path.splitext(f.filename)[-1] or ".mp4"
    tmp    = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    f.save(tmp.name); tmp.close()
    all_plates = []
    try:
        cap = cv2.VideoCapture(tmp.name)
        i   = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            if i % 10 == 0:
                _, found = _process_frame(frame, "video")
                all_plates.extend(found)
            i += 1
        cap.release()
    finally:
        os.unlink(tmp.name)
    return jsonify({"plates": all_plates})

# ══════════════════════════════════════════════════════════════════════════
# RECORDS API
# ══════════════════════════════════════════════════════════════════════════

@app.route("/api/records")
@login_required
def api_records():
    return jsonify(get_all(session["user_id"]))

@app.route("/records/add", methods=["POST"])
@login_required
def records_add():
    data = request.get_json()
    add_plate_manual(data["plate"], data.get("source", "manual"), session["user_id"])
    return jsonify({"status": "ok"})

@app.route("/records/delete/<int:detection_id>", methods=["POST"])
@login_required
def records_delete_one(detection_id):
    delete_by_id(detection_id, session["user_id"])
    return jsonify({"status": "ok"})

@app.route("/records/delete_all", methods=["POST"])
@login_required
def records_delete_all():
    delete_all(session["user_id"])
    return jsonify({"status": "ok"})

@app.route("/export/csv")
@login_required
def export_csv():
    rows = get_all(session["user_id"])
    out  = io.StringIO()
    w    = csv.writer(out)
    w.writerow(["Plate", "Source", "Timestamp"])
    for plate, source, ts, _ in rows:
        w.writerow([plate, source, ts])
    out.seek(0)
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=anpr_records.csv"})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)