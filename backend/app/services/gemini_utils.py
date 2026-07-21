import math


def truncate_and_normalize(vector: list[float], dimensions: int) -> list[float]:
    truncated = vector[:dimensions]
    norm = math.sqrt(sum(x * x for x in truncated))
    if norm == 0:
        return truncated
    return [x / norm for x in truncated]


class TruncatedGeminiEmbeddings:
    """Wraps GoogleGenerativeAIEmbeddings and truncates+L2-renormalizes to a fixed size.

    The `output_dimensionality` kwarg isn't honored by the pinned SDK version - the API
    returns full 3072-dim vectors regardless (confirmed via a real upload: pgvector
    rejected them with "expected 1536 dimensions, not 3072"). gemini-embedding-001 is
    trained with Matryoshka representation learning, which documents truncate-then-
    normalize as a valid alternative to native dimension reduction, so this keeps the
    existing vector(1536) column usable without a schema migration.
    """

    def __init__(self, dimensions: int, **kwargs):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self._dimensions = dimensions
        self._inner = GoogleGenerativeAIEmbeddings(**kwargs)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = await self._inner.aembed_documents(texts)
        return [truncate_and_normalize(v, self._dimensions) for v in vectors]

    async def aembed_query(self, text: str) -> list[float]:
        vector = await self._inner.aembed_query(text)
        return truncate_and_normalize(vector, self._dimensions)
