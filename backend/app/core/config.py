from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    DATABASE_URL: str = "postgresql+asyncpg://raguser:ragpassword@localhost:5432/ragdb"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "")

    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"

    # TEMPORARY (branch experiment/gemini-temp only): lets embeddings/chat run against
    # Gemini instead of OpenAI while the OpenAI test key is out of quota. Must not reach
    # main - default stays "openai" so this is a no-op if ever merged by mistake.
    LLM_PROVIDER: str = "openai"
    GOOGLE_API_KEY: str | None = None
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    GEMINI_EMBEDDING_DIMENSIONS: int = 1536  # matches the existing vector(1536) column - no migration needed
    GEMINI_CHAT_MODEL: str = "gemini-2.0-flash"

    API_KEY: str

    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RETRIEVER_TOP_K: int = 5
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50


settings = Settings()
