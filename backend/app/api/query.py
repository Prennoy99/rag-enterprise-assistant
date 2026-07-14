from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.api.schemas import QueryRequest
from app.core.database import get_db
from app.services.query import QueryService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/query", tags=["query"])
query_service = QueryService()


@router.post("/stream")
async def query_stream(request: QueryRequest, db: AsyncSession = Depends(get_db)):
    async def event_generator():
        try:
            async for token in query_service.query(
                question=request.question,
                document_ids=request.document_ids,
                db=db,
            ):
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
