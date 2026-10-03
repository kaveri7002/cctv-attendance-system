import logging
import numpy as np

logger = logging.getLogger(__name__)


def encode_face(frame, face_bbox):
    try:
        from insightface.app import FaceAnalysis
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("InsightFace is required for embedding generation.") from exc

    analysis = FaceAnalysis(name="buffalo_l")
    analysis.prepare(ctx_id=0, det_size=(640, 640))
    detected = analysis.get(frame, max_num=1)
    if not detected:
        raise ValueError("No face was detected in the supplied image.")

    face = detected[0]
    embedding = np.asarray(face.embedding, dtype=np.float32)
    if embedding.size == 0:
        raise ValueError("Embedding could not be generated.")
    return embedding
