import logging
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from database.db import get_known_embeddings, get_student_by_id, mark_attendance
from recognition.face_detector import detect_faces
from recognition.face_matcher import find_best_match
from notifications.sms_service import send_sms

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, source=0, threshold=0.45, camera_id="Entrance-01"):
        self.source = source
        self.threshold = threshold
        self.camera_id = camera_id
        self.cap = None
        self.camera_available = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._last_status = {"name": "Unknown", "student_id": "", "confidence": 0.0, "status": "Unknown"}
        self._frame_confirmations = {}

    def process_frame(self, frame, tracker_id):
        faces = detect_faces(frame)
        if len(faces) != 1:
            with self._lock:
                self._frame_confirmations.pop(tracker_id, None)
            status = "No face detected" if not faces else "Multiple faces detected"
            self._current_status("Unknown", "", 0.0, status)
            return {**self.get_last_status(), "confirmed_frames": 0}

        embedding = faces[0].get("embedding")
        if embedding is None:
            with self._lock:
                self._frame_confirmations.pop(tracker_id, None)
            self._current_status("Unknown", "", 0.0, "Face could not be encoded")
            return {**self.get_last_status(), "confirmed_frames": 0}

        match = find_best_match(
            embedding,
            get_known_embeddings(),
            threshold=self.threshold,
        )
        if not match:
            with self._lock:
                self._frame_confirmations.pop(tracker_id, None)
            self._current_status("Unknown", "", 0.0, "Unknown")
            return {**self.get_last_status(), "confirmed_frames": 0}

        student = match["student"]
        student_id = student["student_id"]
        student_name = student["name"]
        confidence = round(match["score"], 4)

        with self._lock:
            confirmation = self._frame_confirmations.get(tracker_id)
            if confirmation and confirmation["student_id"] == student_id:
                confirmation["count"] += 1
            else:
                confirmation = {"student_id": student_id, "count": 1, "final_status": None}
                self._frame_confirmations[tracker_id] = confirmation
            confirmed_frames = confirmation["count"]
            final_status = confirmation["final_status"]

        if final_status:
            self._current_status(student_name, student_id, confidence, final_status)
            return {**self.get_last_status(), "confirmed_frames": confirmed_frames}

        self._current_status(student_name, student_id, confidence, "Confirming recognition")
        if confirmed_frames < 3:
            return {**self.get_last_status(), "confirmed_frames": confirmed_frames}

        if not mark_attendance(student_id, student_name, self.camera_id, confidence):
            final_status = "Already Present"
        else:
            try:
                student_record = get_student_by_id(student_id)
                if student_record is None:
                    final_status = "Attendance Marked - Student Contact Missing"
                    logger.error("Student record missing for recognized ID %s.", student_id)
                else:
                    sms_result = send_sms(student_name, student_id, student_record["phone"])
                    final_status = (
                        "Attendance Marked"
                        if sms_result["success"]
                        else "Attendance Marked - SMS Not Sent"
                    )
            except (ValueError, RuntimeError):
                final_status = "Attendance Marked - SMS Failed"
                logger.exception("Attendance was recorded, but SMS delivery failed for %s.", student_id)

        with self._lock:
            confirmation["final_status"] = final_status
        self._current_status(student_name, student_id, confidence, final_status)
        return {**self.get_last_status(), "confirmed_frames": confirmed_frames}

    def _build_placeholder_frame(self, message="Camera unavailable"):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, message, (120, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.putText(frame, "Connect a webcam or CCTV feed to start live recognition.", (60, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 2)
        _, jpeg = cv2.imencode(".jpg", frame)
        return jpeg.tobytes()

    def start(self):
        self.cap = cv2.VideoCapture(self.source)
        if not self.cap.isOpened():
            self.camera_available = False
            self.cap = None
            raise RuntimeError("Unable to open webcam or CCTV feed.")
        self.camera_available = True
        self._stop.clear()

    def stop(self):
        self._stop.set()
        if self.cap is not None:
            self.cap.release()
        self.cap = None
        self.camera_available = False

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
            logger.warning("Camera is not available; streaming placeholder image instead.")
            while not self._stop.is_set():
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + self._build_placeholder_frame() + b"\r\n"
                )
                time.sleep(1.0)
            return

        while not self._stop.is_set():
            ret, frame = self.cap.read()
            if not ret:
                logger.error("Failed to read camera frame.")
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + self._build_placeholder_frame("Camera disconnected") + b"\r\n"
                )
                time.sleep(1.0)
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
                            try:
                                student_record = get_student_by_id(student_id)
                                if student_record:
                                    sms_result = send_sms(
                                        student_name,
                                        student_id,
                                        student_record["phone"],
                                    )
                                    status = (
                                        "Attendance Marked"
                                        if sms_result["success"]
                                        else "Attendance Marked - SMS Not Sent"
                                    )
                                else:
                                    status = "Attendance Marked - Student Contact Missing"
                                    logger.error("Student record missing for recognized ID %s.", student_id)
                            except (ValueError, RuntimeError):
                                status = "Attendance Marked - SMS Failed"
                                logger.exception("Attendance was recorded, but SMS delivery failed for %s.", student_id)
                            self._current_status(student_name, student_id, confidence, status)
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
