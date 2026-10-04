import csv
import io
import logging
import os
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, send_file, session, url_for

from database.db import (
    delete_student,
    get_admin_user,
    get_all_students,
    get_attendance_csv_rows,
    get_dashboard_summary,
    get_default_admin_credentials,
    get_recent_attendance,
    get_student_by_id,
    init_db,
    mark_attendance,
    seed_demo_data,
)
from notifications.sms_service import send_sms
from recognition.camera import CameraManager
from registration.register_student import register_student

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-please-change")

camera_manager = CameraManager(
    source=int(os.getenv("CAMERA_INDEX", 0)),
    threshold=float(os.getenv("RECOGNITION_THRESHOLD", 0.45)),
    camera_id="Entrance-01",
)


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return view_func(*args, **kwargs)

    return wrapped


@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    admin = get_default_admin_credentials()
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = get_admin_user(username)

        if user and user["password"] == password:
            session["logged_in"] = True
            session["username"] = username
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        if username == admin["username"] and password == admin["password"]:
            session["logged_in"] = True
            session["username"] = username
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/dashboard")
@login_required
def dashboard():
    summary = get_dashboard_summary()
    students = get_all_students()
    return render_template("dashboard.html", active="dashboard", summary=summary, students=students)


@app.route("/register")
@login_required
def register_page():
    return render_template("register.html", active="register")


@app.route("/attendance")
@login_required
def attendance_page():
    records = get_recent_attendance(50)
    return render_template("attendance.html", active="attendance", records=records)


@app.route("/live")
@login_required
def live_page():
    return render_template("live.html", active="live")


@app.route("/student/<student_id>")
@login_required
def student_profile(student_id):
    student = get_student_by_id(student_id)
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("dashboard"))
    records = get_recent_attendance(20)
    return render_template("dashboard.html", active="dashboard", student=student, records=records)


@app.route("/api/register", methods=["POST"])
@login_required
def api_register_student():
    try:
        payload = request.get_json(force=True) or {}
        student_data = payload.get("student", {})
        images = payload.get("images", [])
        result = register_student(student_data, images)
        return jsonify({"success": True, "message": "Student registered successfully.", "student": result}), 201
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        logging.exception("Student registration failed")
        return jsonify({"success": False, "error": "Registration failed due to a server error."}), 500


@app.route("/api/delete_student/<student_id>", methods=["POST"])
@login_required
def api_delete_student(student_id):
    try:
        delete_student(student_id)
        return jsonify({"success": True, "message": "Student deleted successfully."})
    except Exception as exc:
        logging.exception("Student deletion failed")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/export_attendance")
@login_required
def export_attendance_csv():
    rows = get_attendance_csv_rows()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_id", "student_name", "date", "entry_time", "camera_id", "confidence", "status"])
    for row in rows:
        writer.writerow([row["student_id"], row["student_name"], row["date"], row["entry_time"], row["camera_id"], row["confidence"], row["status"]])

    memory_file = io.BytesIO()
    memory_file.write(output.getvalue().encode("utf-8"))
    memory_file.seek(0)
    return send_file(memory_file, mimetype="text/csv", as_attachment=True, download_name="attendance.csv")


@app.route("/api/live_status")
@login_required
def live_status():
    return jsonify(camera_manager.get_last_status())


@app.route("/video_feed")
@login_required
def video_feed():
    try:
        if camera_manager.cap is None:
            camera_manager.start()
    except RuntimeError:
        logger.warning("Camera feed unavailable; continuing with placeholder stream.")
    return Response(camera_manager.generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/test_sms", methods=["POST"])
@login_required
def test_sms():
    payload = request.get_json(force=True) or {}
    student_name = payload.get("student_name", "Student")
    student_id = payload.get("student_id", "STU999")
    phone_number = payload.get("phone", os.getenv("DEMO_SMS_RECIPIENT", "+15551234567"))
    result = send_sms(student_name, student_id, phone_number)
    return jsonify({"success": result.get("success", False), "message": result.get("message", "")})


@app.route("/api/simulate_attendance", methods=["POST"])
@login_required
def simulate_attendance():
    payload = request.get_json(force=True) or {}
    student_id = payload.get("student_id")
    if not student_id:
        return jsonify({"success": False, "error": "student_id is required."}), 400

    student = get_student_by_id(student_id)
    if not student:
        return jsonify({"success": False, "error": "Student does not exist."}), 404

    result = mark_attendance(student_id, student["name"], "Simulation", 0.99, "Present")
    if not result:
        return jsonify({"success": False, "error": "Student already marked present today."}), 400

    send_sms(student["name"], student_id, student["phone"])
    return jsonify({"success": True, "message": f"Attendance marked for {student['name']}."})


init_db()
seed_demo_data()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
