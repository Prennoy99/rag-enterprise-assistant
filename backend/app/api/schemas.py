import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    status: Literal["processing", "ready", "failed"]
    chunk_count: int
    created_at: datetime
    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class QueryRequest(BaseModel):
    question: str
    document_ids: list[uuid.UUID] | None = None


class SourceChunk(BaseModel):
    document_id: uuid.UUID
    chunk_index: int
    content: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
