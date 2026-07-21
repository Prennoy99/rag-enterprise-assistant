from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    DATABASE_URL: str = "postgresql+asyncpg://raguser:ragpassword@localhost:5432/ragdb"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    # Which provider serves embeddings/chat - see services/ingestion.py and
    # services/query.py's _build_embeddings()/_build_llm(). Only the active provider's
    # key needs to be set; the other provider's settings can be left blank.
    LLM_PROVIDER: str = "openai"

    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"

    GOOGLE_API_KEY: str | None = None
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    # Matches the existing vector(1536) column so switching providers needs no schema
    # migration - gemini-embedding-001 is Matryoshka-trained, so truncating to this size
    # (see services/gemini_utils.py) is a documented-valid alternative to requesting a
    # smaller native output, which isn't reliably honored by the pinned SDK version.
    GEMINI_EMBEDDING_DIMENSIONS: int = 1536
    # gemini-2.0-flash had 0 free-tier quota when checked; gemini-3.1-flash-lite had the
    # most generous free allowance of the models actually offered (15 RPM / 500 RPD).
    # Google's free-tier lineup shifts over time - re-check aistudio.google.com/rate-limit
    # if this model is ever deprecated or its quota changes.
    GEMINI_CHAT_MODEL: str = "gemini-3.1-flash-lite"

    API_KEY: str

    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RETRIEVER_TOP_K: int = 5
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50

    @model_validator(mode="after")
    def _require_active_provider_key(self) -> "Settings":
        if self.LLM_PROVIDER == "gemini" and not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return self


settings = Settings()
