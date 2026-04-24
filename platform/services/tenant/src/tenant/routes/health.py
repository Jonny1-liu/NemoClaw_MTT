from fastapi import APIRouter
from shared.types import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["infra"])
async def health() -> HealthResponse:
    return HealthResponse(service="tenant")
