import json
import logging
import os
from typing import Any

from backend.app.services.aws_storage import S3Storage, ObjectStorageError
from backend.app.services.snapshot_service import SnapshotService


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Any, context: Any) -> dict[str, Any]:
    logger.info("NewsPulse snapshot invocation started")
    try:
        storage = S3Storage.from_environment()
        result = SnapshotService.validate_lambda_payload(event)
        logger.info("Snapshot payload validated: article_count=%d", len(result.articles))
        response = SnapshotService(None, storage).store_payload(event)  # type: ignore[arg-type]
        logger.info("NewsPulse snapshot upload succeeded: key=%s", response["key"])
        return response
    except (ValueError, TypeError) as error:
        logger.warning("Snapshot payload validation failed: %s", str(error))
        return {"status": "error", "message": "Invalid snapshot payload"}
    except ObjectStorageError:
        logger.exception("NewsPulse snapshot upload failed")
        return {"status": "error", "message": "Snapshot storage is unavailable"}
