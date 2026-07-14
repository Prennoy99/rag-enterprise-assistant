import json
import uuid
from unittest.mock import patch

from app.models.document import DocumentChunk
from app.services.query import SourcesEvent


async def _fake_query(question, document_ids, db):
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="relevant excerpt",
        chunk_index=0,
        embedding=None,
    )
    yield SourcesEvent([chunk])
    yield "Hello"
    yield " world"


async def test_query_stream_emits_sources_before_done(client):
    with patch("app.api.query.query_service.query", new=_fake_query):
        response = await client.post(
            "/api/v1/query/stream", json={"question": "test?", "document_ids": None}
        )

    assert response.status_code == 200
    events = [line[len("data: "):] for line in response.text.split("\n\n") if line.strip()]

    assert events[0].startswith("[SOURCES] ")
    sources = json.loads(events[0][len("[SOURCES] "):])
    assert sources[0]["content"] == "relevant excerpt"
    assert sources[0]["chunk_index"] == 0
    assert events[1] == "Hello"
    assert events[2] == " world"
    assert events[-1] == "[DONE]"


async def _fake_query_error(question, document_ids, db):
    yield SourcesEvent([])
    raise RuntimeError("boom")
    yield  # pragma: no cover - unreachable, keeps this an async generator


async def test_query_stream_reports_errors_and_still_terminates(client):
    with patch("app.api.query.query_service.query", new=_fake_query_error):
        response = await client.post(
            "/api/v1/query/stream", json={"question": "test?", "document_ids": None}
        )

    events = [line[len("data: "):] for line in response.text.split("\n\n") if line.strip()]
    assert any(e.startswith("[ERROR]") for e in events)
    assert events[-1] == "[DONE]"
