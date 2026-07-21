import uuid
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.document import Document, DocumentChunk


def _build_embeddings():
    if settings.LLM_PROVIDER == "gemini":
        from app.services.gemini_utils import TruncatedGeminiEmbeddings

        return TruncatedGeminiEmbeddings(
            dimensions=settings.GEMINI_EMBEDDING_DIMENSIONS,
            model=settings.GEMINI_EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            task_type="RETRIEVAL_DOCUMENT",
        )
    return OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY,
    )


class IngestionService:
    def __init__(self):
        self.embeddings = _build_embeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    async def ingest_document(self, document_id: uuid.UUID, file_path: str) -> None:
        async with AsyncSessionLocal() as db:
            try:
                raw_docs = self._load_file(file_path)
                full_text = "\n\n".join(doc.page_content for doc in raw_docs)
                chunks = self.text_splitter.split_text(full_text)
                vectors = await self.embeddings.aembed_documents(chunks)

                chunk_objects = [
                    DocumentChunk(
                        document_id=document_id,
                        content=chunk,
                        chunk_index=i,
                        embedding=vector,
                    )
                    for i, (chunk, vector) in enumerate(zip(chunks, vectors))
                ]
                db.add_all(chunk_objects)

                result = await db.execute(select(Document).where(Document.id == document_id))
                doc = result.scalar_one()
                doc.status = "ready"
                doc.chunk_count = len(chunks)
                await db.commit()

            except Exception as e:
                await db.rollback()
                result = await db.execute(select(Document).where(Document.id == document_id))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = "failed"
                    await db.commit()
                raise e

    def _load_file(self, file_path: str):
        ext = Path(file_path).suffix.lower()
        if ext == ".pdf":
            return PyPDFLoader(file_path).load()
        elif ext in (".docx", ".doc"):
            return Docx2txtLoader(file_path).load()
        else:
            from langchain_community.document_loaders import TextLoader
            return TextLoader(file_path).load()
