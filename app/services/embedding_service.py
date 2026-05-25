import json
import numpy as np
from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def create_embedding(text: str) -> list[float]:
    embedding = embedding_model.encode(text)

    return embedding.tolist()


def embedding_to_json(embedding: list[float]) -> str:
    return json.dumps(embedding)


def json_to_embedding(embedding_json: str) -> np.ndarray:
    return np.array(json.loads(embedding_json))


def cosine_similarity(vector_a, vector_b) -> float:
    vector_a = np.array(vector_a)
    vector_b = np.array(vector_b)

    dot_product = np.dot(vector_a, vector_b)
    norm_a = np.linalg.norm(vector_a)
    norm_b = np.linalg.norm(vector_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)