from fastapi import APIRouter

from backend.app.schemas.articles import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Check API health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")
