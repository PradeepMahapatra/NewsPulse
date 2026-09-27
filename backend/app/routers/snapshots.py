from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from backend.app.dependencies import get_snapshot_service
from backend.app.schemas.snapshots import SnapshotResponse
from backend.app.services.aws_storage import ObjectStorageConfigurationError, ObjectStorageError
from backend.app.services.snapshot_service import SnapshotService


router = APIRouter(prefix="/articles", tags=["snapshots"])


@router.post(
    "/snapshot",
    response_model=SnapshotResponse,
    summary="Write a safe article snapshot to private S3 storage",
)
def create_snapshot(
    service: SnapshotService = Depends(get_snapshot_service),
) -> SnapshotResponse:
    try:
        return SnapshotResponse(**service.create_snapshot())
    except ObjectStorageConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ObjectStorageError as error:
        raise HTTPException(status_code=502, detail="Snapshot storage is unavailable") from error
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from error
