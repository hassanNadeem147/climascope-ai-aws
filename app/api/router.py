from fastapi import APIRouter
from app.api.routers.auth import router as auth_router
from app.api.routers.model_router import router as model_router
api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(model_router)