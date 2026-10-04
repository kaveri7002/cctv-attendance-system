# CCTV Face Recognition Biometric Attendance System

This project provides a complete Flask-based CCTV attendance system for a college campus. It uses OpenCV + InsightFace for face detection and embedding generation, SQLite for persistent storage, and Flask templates for the dashboard and registration workflows.

## Features

- Student registration with webcam capture
- Multi-image enrollment for better recognition accuracy
- Face quality validation (lighting and blurriness checks)
- Real-time CCTV recognition via webcam stream
- Duplicate attendance prevention per student per day
- SQLite database for students, embeddings, and attendance logs
- Admin login and dashboard
- Attendance export to CSV
- SMS notification support with a demo mode

## Project structure

```text
cctv_attendance/
├── app.py
├── requirements.txt
├── .env.example
├── database/
│   └── attendance.db
├── recognition/
│   ├── __init__.py
│   ├── face_detector.py
│   ├── face_encoder.py
│   ├── face_matcher.py
│   └── camera.py
├── registration/
│   ├── __init__.py
│   └── register_student.py
├── notifications/
│   ├── __init__.py
│   └── sms_service.py
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   ├── register.html
│   ├── attendance.html
│   └── live.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
└── README.md
```

## Installation

1. Install Python 3.10 or newer.
2. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a local environment file:

```bash
cp .env.example .env
```

Then update `.env` with your preferred secret values.

## Database setup

The database is created automatically when the app starts. The initial schema includes:

- `students`
- `face_embeddings`
- `attendance`
- `admin_users`

## Running the app

```bash
python app.py
```

Then open `http://127.0.0.1:5000` to access the login page.

Default admin credentials are loaded from the environment file (`.env`). You can change them here:

- `ADMIN_USERNAME=admin`
- `ADMIN_PASSWORD=admin123`

For a production deployment, set unique values in `.env` and do not share them in source control.

## Registering students

1. Log in to the admin dashboard.
2. Open the registration page.
3. Fill in student details.
4. Allow webcam access.
5. Capture several good-quality face images from different angles.
6. Submit the registration form.

## Testing the recognition flow

A demo mode can be enabled through `.env` with `TEST_MODE=true`. When enabled, the app inserts sample students and sample attendance entries if the database is empty.

## SMS notification

The app uses environment variables to configure SMS sending. Set `SMS_PROVIDER=demo` to print notifications to the console without sending a real SMS.

## Notes

- The application does not store raw face images after embeddings are generated. It keeps only the embedding vectors.
- If a camera is unavailable or no face is detected, the app logs the event and shows a helpful message.
- Attendance is prevented for duplicate entries for the same student on the same day.
