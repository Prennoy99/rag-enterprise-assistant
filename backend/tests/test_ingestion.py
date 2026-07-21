from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.document import Document, DocumentChunk
from app.services.ingestion import IngestionService


async def _seed_processing_document(db_session) -> Document:
    doc = Document(
        filename="f.txt",
        original_filename="f.txt",
        file_size=10,
        mime_type="text/plain",
        status="processing",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def test_ingest_document_marks_ready_and_creates_chunks(db_session, tmp_path):
    doc = await _seed_processing_document(db_session)

    file_path = tmp_path / "f.txt"
    file_path.write_text("Hello world. " * 50)

    service = IngestionService()
    expected_chunks = service.text_splitter.split_text(file_path.read_text())

    # Patch on the class, not the instance: OpenAIEmbeddings is a Pydantic v1 model,
    # which rejects setting attributes that aren't declared fields directly on an
    # instance. Patching type(service.embeddings) instead bypasses that restriction
    # (attribute lookup falls through to the class) and works for either provider.
    with patch.object(
        type(service.embeddings),
        "aembed_documents",
        new=AsyncMock(return_value=[[0.0] * 1536 for _ in expected_chunks]),
    ):
        await service.ingest_document(document_id=doc.id, file_path=str(file_path))

    # populate_existing: ingest_document updates this row via a separate session
    # (AsyncSessionLocal). Without this, SQLAlchemy's identity map returns doc's
    # already-loaded (now-stale) attributes instead of re-reading the committed row.
    result = await db_session.execute(
        select(Document).where(Document.id == doc.id).execution_options(populate_existing=True)
    )
    refreshed = result.scalar_one()
    assert refreshed.status == "ready"
    assert refreshed.chunk_count == len(expected_chunks)

    chunk_result = await db_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )
    assert len(chunk_result.scalars().all()) == len(expected_chunks)


async def test_ingest_document_marks_failed_on_load_error(db_session, tmp_path):
    doc = await _seed_processing_document(db_session)
    missing_path = tmp_path / "does-not-exist.txt"

    service = IngestionService()
    with pytest.raises(Exception):
        await service.ingest_document(document_id=doc.id, file_path=str(missing_path))

    result = await db_session.execute(
        select(Document).where(Document.id == doc.id).execution_options(populate_existing=True)
    )
    refreshed = result.scalar_one()
    assert refreshed.status == "failed"
