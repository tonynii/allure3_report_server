import logging

from app.config import settings

logger = logging.getLogger(__name__)

_HAS_EMBEDDING = bool(settings.embedding_base_url and settings.embedding_api_key)
MAX_EMBEDDING_CHARS = 6000


async def embed_text(text: str) -> list[float] | None:
    if not _HAS_EMBEDDING or not text:
        return None

    truncated = text
    if len(text) > MAX_EMBEDDING_CHARS:
        truncated = text[:4000] + "\n...[truncated]...\n" + text[-2000:]

    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.embedding_base_url}/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={"model": settings.embedding_model, "input": truncated},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except Exception as e:
        logger.warning("Embedding API call failed: %s", e)
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vector length mismatch")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
