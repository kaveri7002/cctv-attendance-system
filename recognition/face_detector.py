import logging
from typing import List, Dict, Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

FACE_MODEL = None


def get_face_analysis_model():
    global FACE_MODEL
    if FACE_MODEL is not None:
        return FACE_MODEL

    try:
        from insightface.app import FaceAnalysis
    except Exception as exc:  # pragma: no cover - import-time path validation handled in runtime
        raise RuntimeError("InsightFace is required for face detection. Install requirements.txt first.") from exc

    FACE_MODEL = FaceAnalysis(name="buffalo_l")
    FACE_MODEL.prepare(ctx_id=0, det_size=(640, 640))
    return FACE_MODEL


def detect_faces(frame):
    try:
        model = get_face_analysis_model()
    except RuntimeError:
        logger.warning("Face recognition dependencies are not available; detection skipped.")
        return []

    try:
        raw_faces = model.get(frame, max_num=0)
    except Exception as exc:
        logger.error("Face detection failed: %s", exc)
        return []

    faces = []
    for raw_face in raw_faces:
        bbox = raw_face.bbox.astype(int)
        x1, y1, x2, y2 = [max(0, int(v)) for v in bbox[:4]]
        if x2 <= x1 or y2 <= y1:
            continue

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        faces.append({
            "bbox": (x1, y1, x2, y2),
            "brightness": brightness,
            "blur": blur,
            "confidence": float(getattr(raw_face, "det_score", 0.0)),
            "embedding": getattr(raw_face, "embedding", None),
        })

    return faces


def face_quality_pass(face_data):
    brightness = face_data.get("brightness", 0)
    blur = face_data.get("blur", 0)
    if brightness < 35 or blur < 50:
        return False
    return True
