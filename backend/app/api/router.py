from fastapi import APIRouter, Depends
from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.core.security import verify_api_key

api_router = APIRouter(dependencies=[Depends(verify_api_key)])
api_router.include_router(documents_router)
api_router.include_router(query_router)
