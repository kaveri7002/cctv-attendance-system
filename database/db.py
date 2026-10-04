import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "attendance.db"


def get_default_admin_credentials():
    return {
        "username": os.getenv("ADMIN_USERNAME", "admin"),
        "password": os.getenv("ADMIN_PASSWORD", "admin123"),
    }


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                semester TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                embedding TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                student_name TEXT NOT NULL,
                date TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                camera_id TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        admin = get_default_admin_credentials()
        conn.execute(
            """
            INSERT OR IGNORE INTO admin_users (username, password, name)
            VALUES (?, ?, 'Administrator')
            """,
            (admin["username"], admin["password"]),
        )


def create_student(student_id, name, department, semester, phone, email):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO students (student_id, name, department, semester, phone, email)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (student_id, name, department, semester, phone, email),
        )
        return cursor.lastrowid


def get_student_by_id(student_id):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()


def get_student_by_row_id(student_id):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()


def get_all_students():
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM students ORDER BY created_at DESC"
        ).fetchall()


def get_student_by_name(name):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE name = ?",
            (name,),
        ).fetchone()


def save_embedding(student_id, embedding):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO face_embeddings (student_id, embedding) VALUES (?, ?)",
            (student_id, json.dumps([float(item) for item in embedding])),
        )


def get_known_embeddings():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.student_id, s.name, e.embedding
            FROM face_embeddings e
            INNER JOIN students s ON s.student_id = e.student_id
            """
        ).fetchall()

    data = []
    for row in rows:
        try:
            embedding = json.loads(row["embedding"])
            data.append({"student_id": row["student_id"], "name": row["name"], "embedding": embedding})
        except (TypeError, ValueError):
            continue
    return data


def mark_attendance(student_id, student_name, camera_id, confidence, status="Present"):
    today = datetime.now().strftime("%d-%m-%Y")
    current_time = datetime.now().strftime("%I:%M:%S %p")
    with get_connection() as conn:
        exists = conn.execute(
            """
            SELECT id FROM attendance
            WHERE student_id = ? AND date = ? AND status = 'Present'
            """,
            (student_id, today),
        ).fetchone()
        if exists:
            return False

        conn.execute(
            """
            INSERT INTO attendance (student_id, student_name, date, entry_time, camera_id, confidence, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (student_id, student_name, today, current_time, camera_id, float(confidence), status),
        )
        return True


def get_recent_attendance(limit=20):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM attendance ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def get_dashboard_summary():
    today = datetime.now().strftime("%d-%m-%Y")
    with get_connection() as conn:
        total_students = conn.execute("SELECT COUNT(*) AS total FROM students").fetchone()["total"]
        today_attendance = conn.execute(
            "SELECT COUNT(*) AS total FROM attendance WHERE date = ?",
            (today,),
        ).fetchone()["total"]
        attendance_percentage = round((today_attendance / total_students) * 100, 2) if total_students else 0.0
        recent_entries = conn.execute(
            "SELECT * FROM attendance ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
    return {
        "total_students": total_students,
        "today_attendance": today_attendance,
        "attendance_percentage": attendance_percentage,
        "recent_entries": recent_entries,
    }


def get_admin_user(username):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM admin_users WHERE username = ?",
            (username,),
        ).fetchone()


def delete_student(student_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM face_embeddings WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))


def get_attendance_csv_rows():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT student_id, student_name, date, entry_time, camera_id, confidence, status FROM attendance ORDER BY id DESC"
        ).fetchall()
    return rows


def seed_demo_data():
    with get_connection() as conn:
        student_count = conn.execute("SELECT COUNT(*) AS total FROM students").fetchone()["total"]
        if student_count > 0:
            return

        sample_students = [
            ("STU001", "Rahul", "Computer Science", "Semester 6", "+919000000001", "rahul@campus.edu"),
            ("STU002", "Priya", "Electronics", "Semester 4", "+919000000002", "priya@campus.edu"),
        ]
        for payload in sample_students:
            conn.execute(
                "INSERT INTO students (student_id, name, department, semester, phone, email) VALUES (?, ?, ?, ?, ?, ?)",
                payload,
            )

        conn.execute(
            "INSERT INTO attendance (student_id, student_name, date, entry_time, camera_id, confidence, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("STU001", "Rahul", datetime.now().strftime("%d-%m-%Y"), datetime.now().strftime("%I:%M:%S %p"), "Entrance-01", 0.97, "Present"),
        )
