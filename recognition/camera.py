import logging
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from database.db import get_known_embeddings, mark_attendance
from recognition.face_detector import detect_faces
from recognition.face_matcher import find_best_match

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, source=0, threshold=0.45, camera_id="Entrance-01"):
        self.source = source
        self.threshold = threshold
        self.camera_id = camera_id
        self.cap = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._last_status = {"name": "Unknown", "student_id": "", "confidence": 0.0, "status": "Unknown"}

    def start(self):
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            raise RuntimeError("Unable to open webcam or CCTV feed.")
        self._stop.clear()

    def stop(self):
        self._stop.set()
        if self.cap is not None:
            self.cap.release()

    def _current_status(self, name, student_id, confidence, status):
        with self._lock:
            self._last_status = {
                "name": name,
                "student_id": student_id,
                "confidence": confidence,
                "status": status,
            }

    def get_last_status(self):
        with self._lock:
            return dict(self._last_status)

    def generate_frames(self):
        if self.cap is None:
            raise RuntimeError("Camera not started.")

        while not self._stop.is_set():
            ret, frame = self.cap.read()
            if not ret:
                logger.error("Failed to read camera frame.")
                time.sleep(0.5)
                continue

            frame = cv2.flip(frame, 1)
            detected_faces = detect_faces(frame)
            if detected_faces:
                for face in detected_faces:
                    x1, y1, x2, y2 = face["bbox"]
                    embedding = face.get("embedding")
                    if embedding is None:
                        continue

                    known_faces = get_known_embeddings()
                    match = find_best_match(embedding, known_faces, threshold=self.threshold)
                    if match:
                        student = match["student"]
                        student_name = student["name"]
                        student_id = student["student_id"]
                        confidence = round(match["score"], 4)
                        self._current_status(student_name, student_id, confidence, "Recognized")
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{student_name} ({student_id}) {confidence}", (x1, max(0, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                        if mark_attendance(student_id, student_name, self.camera_id, confidence):
                            self._current_status(student_name, student_id, confidence, "Attendance Marked")
                    else:
                        self._current_status("Unknown", "", 0.0, "Unknown")
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(frame, "Unknown", (x1, max(0, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            else:
                self._current_status("Unknown", "", 0.0, "No Face")

            _, jpeg = cv2.imencode(".jpg", frame)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
            )
            time.sleep(0.1)
