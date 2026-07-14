import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import QueryRequest, SourceChunk
from app.core.database import get_db
from app.services.query import QueryService, SourcesEvent

router = APIRouter(prefix="/query", tags=["query"])
query_service = QueryService()


@router.post("/stream")
async def query_stream(request: QueryRequest, db: AsyncSession = Depends(get_db)):
    async def event_generator():
        try:
            async for item in query_service.query(
                question=request.question,
                document_ids=request.document_ids,
                db=db,
            ):
                if isinstance(item, SourcesEvent):
                    sources = [
                        SourceChunk(document_id=c.document_id, chunk_index=c.chunk_index, content=c.content)
                        for c in item.chunks
                    ]
                    payload = json.dumps([s.model_dump(mode="json") for s in sources])
                    yield f"data: [SOURCES] {payload}\n\n"
                else:
                    yield f"data: {item}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
