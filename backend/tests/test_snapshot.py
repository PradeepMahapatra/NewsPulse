import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.models import Base
from backend.app.database.repository import ArticleRepository
from backend.app.services.aws_storage import (
    ObjectStorageConfigurationError,
    ObjectStorageError,
    S3Storage,
)
from backend.app.services.news_ingestion import NewsArticle
from backend.app.services.snapshot_service import SnapshotService
from backend.lambda_handler import handler


class FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


class FailingS3Client:
    def put_object(self, **kwargs):
        raise RuntimeError("private AWS detail")


def make_repository() -> ArticleRepository:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return ArticleRepository(sessionmaker(bind=engine, expire_on_commit=False))


def test_snapshot_serialization_and_sensitive_data_exclusion() -> None:
    repository = make_repository()
    repository.save_article(
        NewsArticle(
            id="article-1",
            title="Safe title",
            description="Safe description",
            url="https://example.com",
            language="en",
        )
    )
    client = FakeS3Client()
    service = SnapshotService(repository, S3Storage("bucket", "us-east-1", client))

    result = service.create_snapshot()
    document = json.loads(client.calls[0]["Body"])

    assert result["status"] == "success"
    assert result["article_count"] == 1
    assert result["key"].startswith("newspulse/snapshots/")
    assert client.calls[0]["ServerSideEncryption"] == "AES256"
    serialized = json.dumps(document)
    assert "DATABASE_URL" not in serialized
    assert "CURRENTS_API_KEY" not in serialized
    assert "AWS_ACCESS_KEY_ID" not in serialized
    assert document["articles"][0]["title"] == "Safe title"


def test_s3_key_generation_and_upload_failure() -> None:
    generated_at = datetime(2026, 9, 27, 12, 30, tzinfo=timezone.utc)
    client = FakeS3Client()
    storage = S3Storage("bucket", "us-east-1", client)
    assert storage.put_json(b"{}", generated_at) == (
        "newspulse/snapshots/2026/09/27/articles-20260927T123000Z.json"
    )

    with pytest.raises(ObjectStorageError, match="upload failed"):
        S3Storage("bucket", "us-east-1", FailingS3Client()).put_json(b"{}", generated_at)


def test_missing_s3_configuration(monkeypatch) -> None:
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    with pytest.raises(ObjectStorageConfigurationError):
        S3Storage.from_environment()


def test_lambda_payload_validation_and_success(monkeypatch) -> None:
    client = FakeS3Client()
    monkeypatch.setattr(
        S3Storage,
        "from_environment",
        classmethod(lambda cls: S3Storage("bucket", "us-east-1", client)),
    )
    result = handler({"snapshot_type": "articles", "articles": [{"title": "Safe"}]}, None)
    assert result["status"] == "success"
    assert result["article_count"] == 1
    assert len(client.calls) == 1


def test_lambda_malformed_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        S3Storage,
        "from_environment",
        classmethod(lambda cls: S3Storage("bucket", "us-east-1", FakeS3Client())),
    )
    assert handler({"wrong": "shape"}, None) == {
        "status": "error",
        "message": "Invalid snapshot payload",
    }
