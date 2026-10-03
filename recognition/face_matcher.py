import numpy as np


def cosine_similarity(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    if a.size == 0 or b.size == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def find_best_match(embedding, known_embeddings, threshold=0.45):
    best_match = None
    best_score = -1.0

    for candidate in known_embeddings:
        score = cosine_similarity(embedding, candidate["embedding"])
        if score > best_score:
            best_match = candidate
            best_score = score

    if best_match and best_score >= threshold:
        return {"student": best_match, "score": best_score}
    return None
