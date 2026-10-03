import base64
import cv2
import numpy as np

from database.db import create_student, get_student_by_id, save_embedding
from recognition.face_detector import detect_faces, face_quality_pass


def _decode_image(encoded_image):
    if not encoded_image:
        raise ValueError("No face images were provided for registration.")
    data = encoded_image.split(",", 1)[1] if "," in encoded_image else encoded_image
    try:
        image_bytes = base64.b64decode(data)
    except Exception as exc:
        raise ValueError("The uploaded image is not valid base64 data.") from exc

    array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("The uploaded image could not be decoded.")
    return frame


def register_student(student_data, image_list):
    student_id = (student_data.get("student_id") or "").strip()
    name = (student_data.get("name") or "").strip()
    department = (student_data.get("department") or "").strip()
    semester = (student_data.get("semester") or "").strip()
    phone = (student_data.get("phone") or "").strip()
    email = (student_data.get("email") or "").strip()

    if not all([student_id, name, department, semester, phone, email]):
        raise ValueError("All student fields are required.")

    if get_student_by_id(student_id):
        raise ValueError(f"Student {student_id} is already registered.")

    if not image_list:
        raise ValueError("At least one face image is required during registration.")

    embeddings = []
    for index, encoded in enumerate(image_list[:5], start=1):
        frame = _decode_image(encoded)
        faces = detect_faces(frame)
        if len(faces) != 1:
            raise ValueError(f"Image {index} must contain exactly one face. Multiple or no faces were detected.")

        face = faces[0]
        if not face_quality_pass(face):
            raise ValueError(f"Image {index} is too dark or blurry. Capture a clearer face image.")

        embedding = face.get("embedding")
        if embedding is None or len(embedding) == 0:
            raise ValueError(f"Image {index} could not generate a valid face embedding.")

        embeddings.append(embedding)

    if len(embeddings) == 0:
        raise ValueError("No valid embeddings were produced for registration.")

    create_student(student_id, name, department, semester, phone, email)
    for embedding in embeddings:
        save_embedding(student_id, embedding)

    return {
        "student_id": student_id,
        "name": name,
        "department": department,
        "semester": semester,
        "phone": phone,
        "email": email,
        "embeddings_count": len(embeddings),
    }
