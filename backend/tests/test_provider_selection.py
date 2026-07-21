from app.core.config import settings
from app.services import ingestion as ingestion_module
from app.services import query as query_module


def test_ingestion_defaults_to_openai():
    embeddings = ingestion_module._build_embeddings()
    assert type(embeddings).__name__ == "OpenAIEmbeddings"


def test_query_defaults_to_openai():
    embeddings = query_module._build_embeddings()
    llm = query_module._build_llm()
    assert type(embeddings).__name__ == "OpenAIEmbeddings"
    assert type(llm).__name__ == "ChatOpenAI"


def test_ingestion_uses_gemini_when_selected(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "fake-test-key")

    embeddings = ingestion_module._build_embeddings()

    assert type(embeddings).__name__ == "TruncatedGeminiEmbeddings"
    assert embeddings._dimensions == settings.GEMINI_EMBEDDING_DIMENSIONS


def test_query_uses_gemini_when_selected(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "fake-test-key")

    embeddings = query_module._build_embeddings()
    llm = query_module._build_llm()

    assert type(embeddings).__name__ == "TruncatedGeminiEmbeddings"
    assert type(llm).__name__ == "ChatGoogleGenerativeAI"
