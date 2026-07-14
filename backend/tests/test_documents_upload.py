import io
import zipfile
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def mock_ingestion():
    # Upload tests exercise validation only; ingestion (and its OpenAI calls) is covered separately.
    with patch("app.api.documents.ingestion_service.ingest_document", new=AsyncMock(return_value=None)):
        yield


async def test_upload_valid_text_file(client, valid_txt_bytes):
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("notes.txt", valid_txt_bytes, "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processing"
    assert body["mime_type"] == "text/plain"
    assert body["original_filename"] == "notes.txt"


async def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 0.0001)  # ~100 bytes
    content = b"x" * 1000
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("big.txt", content, "text/plain")},
    )
    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()


async def test_upload_rejects_spoofed_content_type(client):
    # Claims to be a PDF via the header, but the bytes are a PNG - content sniffing
    # must catch this even though the client-supplied header lies.
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("fake.pdf", png_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    assert "unsupported file type" in response.json()["detail"].lower()


async def test_upload_detects_docx_despite_generic_zip_signature(client):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("word/document.xml", "<w:document></w:document>")
        zf.writestr("[Content_Types].xml", "<Types></Types>")
    docx_bytes = buffer.getvalue()

    response = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("report.docx", docx_bytes, "application/octet-stream")},
    )
    assert response.status_code == 201
    assert (
        response.json()["mime_type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
