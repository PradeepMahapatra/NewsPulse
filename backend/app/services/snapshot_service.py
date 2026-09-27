from datetime import datetime, timezone
import json
from typing import Any

from backend.app.database.repository import ArticleRepository
from backend.app.schemas.articles import ArticleResponse
from backend.app.schemas.snapshots import SnapshotPayload
from backend.app.services.aws_storage import (
    ObjectStorageConfigurationError,
    S3Storage,
)


class SnapshotService:
    def __init__(self, repository: ArticleRepository | None, storage: S3Storage | None) -> None:
        self._repository = repository
        self._storage = storage

    def create_snapshot(self) -> dict[str, Any]:
        if self._repository is None:
            raise RuntimeError("repository is required for database snapshots")
        if self._storage is None:
            raise ObjectStorageConfigurationError("S3_BUCKET_NAME is not configured")
        generated_at = datetime.now(timezone.utc)
        articles = self._repository.list_all_articles()
        payload = SnapshotPayload(
            snapshot_type="articles",
            articles=[ArticleResponse.from_record(article).model_dump(mode="json") for article in articles],
        )
        document = {
            "generated_at": generated_at.isoformat(),
            "article_count": len(payload.articles),
            "snapshot_type": payload.snapshot_type,
            "articles": payload.articles,
        }
        encoded = json.dumps(document, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        key = self._storage.put_json(encoded, generated_at)
        return {
            "status": "success",
            "bucket": self._storage.bucket,
            "key": key,
            "article_count": len(payload.articles),
            "generated_at": generated_at,
        }

    @staticmethod
    def validate_lambda_payload(event: Any) -> SnapshotPayload:
        if not isinstance(event, dict):
            raise ValueError("event must be a JSON object")
        return SnapshotPayload.model_validate(event)

    def store_payload(self, event: Any) -> dict[str, Any]:
        if self._storage is None:
            raise ObjectStorageConfigurationError("S3_BUCKET_NAME is not configured")
        payload = self.validate_lambda_payload(event)
        generated_at = datetime.now(timezone.utc)
        document = {
            "generated_at": generated_at.isoformat(),
            "article_count": len(payload.articles),
            "snapshot_type": payload.snapshot_type,
            "articles": payload.articles,
        }
        encoded = json.dumps(document, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        key = self._storage.put_json(encoded, generated_at)
        return {
            "status": "success",
            "bucket": self._storage.bucket,
            "key": key,
            "article_count": len(payload.articles),
            "generated_at": generated_at,
        }
