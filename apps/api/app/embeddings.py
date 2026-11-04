from collections.abc import Sequence
from functools import lru_cache
from typing import Any

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSIONS = 384


@lru_cache(maxsize=1)
def _model() -> Any:
    # Imported here because it adds about 550 MB of memory, which the web process doesn't need.
    from fastembed import TextEmbedding

    return TextEmbedding(MODEL_NAME)


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    return [vector.tolist() for vector in _model().embed(list(texts))]
