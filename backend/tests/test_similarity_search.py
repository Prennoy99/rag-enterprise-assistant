import pytest

from app.models.document import Document, DocumentChunk
from app.services.query import QueryService


async def _seed_document_with_chunk(db_session, content: str, embedding: list[float]):
    doc = Document(
        filename="f.txt",
        original_filename="f.txt",
        file_size=10,
        mime_type="text/plain",
        status="ready",
    )
    db_session.add(doc)
    await db_session.flush()
    chunk = DocumentChunk(document_id=doc.id, content=content, chunk_index=0, embedding=embedding)
    db_session.add(chunk)
    await db_session.flush()
    return doc, chunk


async def test_similarity_search_filters_by_document_ids(db_session):
    service = QueryService()
    vec_a = [1.0] + [0.0] * 1535
    vec_b = [0.0, 1.0] + [0.0] * 1534

    doc_a, chunk_a = await _seed_document_with_chunk(db_session, "from doc A", vec_a)
    _doc_b, _chunk_b = await _seed_document_with_chunk(db_session, "from doc B", vec_b)
    await db_session.commit()

    results = await service._similarity_search(vec_a, [doc_a.id], db_session, top_k=5)

    assert {r.id for r in results} == {chunk_a.id}


async def test_similarity_search_rejects_non_uuid_filter_instead_of_interpolating_it(db_session):
    """Regression test for the string-interpolated IN-clause this replaced.

    document_ids are normally Pydantic-validated as uuid.UUID before reaching this
    method, but if that validation is ever loosened, a malicious string must fail
    safely as a parameter-binding error, not get concatenated into executable SQL.
    """
    service = QueryService()
    vec = [1.0] + [0.0] * 1535
    await _seed_document_with_chunk(db_session, "content", vec)
    await db_session.commit()

    malicious_id = "'; DROP TABLE documents; --"

    with pytest.raises(Exception):
        await service._similarity_search(vec, [malicious_id], db_session, top_k=5)
