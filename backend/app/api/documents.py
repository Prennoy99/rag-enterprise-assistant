import io
import os
import uuid
import zipfile
from pathlib import Path

import magic
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import DocumentListResponse, DocumentResponse
from app.core.config import settings
from app.core.database import get_db
from app.models.document import Document
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/documents", tags=["documents"])
ingestion_service = IngestionService()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

UPLOAD_READ_CHUNK_SIZE = 1024 * 1024
DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _detect_mime(content: bytes, filename: str) -> str:
    detected = magic.from_buffer(content, mime=True)
    # libmagic often reports .docx (a zip container) as generic application/zip; confirm via its internal structure.
    if detected == "application/zip" and filename.lower().endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                if "word/document.xml" in zf.namelist():
                    return DOCX_MIME_TYPE
        except zipfile.BadZipFile:
            pass
    return detected


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    content = bytearray()
    while chunk := await file.read(UPLOAD_READ_CHUNK_SIZE):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise HTTPException(status_code=400, detail=f"File too large. Max: {settings.MAX_FILE_SIZE_MB}MB")
    content = bytes(content)

    # Trust the sniffed content type, not the client-supplied header, which is trivially spoofable.
    detected_mime = _detect_mime(content, file.filename)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {detected_mime}")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True)
    saved_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = upload_dir / saved_filename

    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        filename=saved_filename,
        original_filename=file.filename,
        file_size=len(content),
        mime_type=detected_mime,
        status="processing",
    )
    db.add(doc)
    await db.flush()

    background_tasks.add_task(
        ingestion_service.ingest_document,
        document_id=doc.id,
        file_path=str(file_path),
    )
    return doc


@router.get("/", response_model=DocumentListResponse)
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    documents = result.scalars().all()
    return DocumentListResponse(documents=list(documents), total=len(documents))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = Path(settings.UPLOAD_DIR) / doc.filename
    if file_path.exists():
        os.remove(file_path)
    await db.delete(doc)
