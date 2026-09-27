import json

import pytest

from aws import lambda_function


class FakeS3Client:
    def __init__(self) -> None:
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)


def test_lambda_uploads_safe_snapshot(monkeypatch) -> None:
    client = FakeS3Client()
    monkeypatch.setenv("S3_BUCKET_NAME", "newspulse-test")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setattr(lambda_function.boto3, "client", lambda *args, **kwargs: client)

    result = lambda_function.handler(
        {"snapshot_type": "articles", "articles": [{"title": "Safe smoke test"}]}, None
    )

    assert result["status"] == "success"
    assert result["article_count"] == 1
    assert client.calls[0]["ServerSideEncryption"] == "AES256"
    body = client.calls[0]["Body"].decode()
    assert "DATABASE_URL" not in body
    assert "CURRENTS_API_KEY" not in body


def test_lambda_rejects_malformed_payload(monkeypatch) -> None:
    monkeypatch.setenv("S3_BUCKET_NAME", "newspulse-test")
    assert lambda_function.handler({"snapshot_type": "wrong", "articles": []}, None) == {
        "status": "error",
        "message": "Invalid snapshot payload",
    }
