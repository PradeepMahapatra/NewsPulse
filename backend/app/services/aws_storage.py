from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Protocol

from dotenv import load_dotenv


class ObjectStorageError(RuntimeError):
    """Raised when a snapshot cannot be written to object storage."""


class ObjectStorageConfigurationError(ObjectStorageError):
    """Raised when required non-secret AWS configuration is missing."""


class ObjectStorageClient(Protocol):
    def put_object(self, **kwargs: Any) -> Any:
        ...


@dataclass(frozen=True)
class S3Storage:
    bucket: str
    region: str
    client: ObjectStorageClient
    prefix: str = "newspulse/snapshots"

    @classmethod
    def from_environment(cls) -> "S3Storage":
        load_dotenv()
        bucket = os.getenv("S3_BUCKET_NAME")
        region = os.getenv("AWS_REGION", "us-east-1")
        if not bucket:
            raise ObjectStorageConfigurationError("S3_BUCKET_NAME is not configured")
        import boto3

        return cls(bucket=bucket, region=region, client=boto3.client("s3", region_name=region))

    def put_json(self, payload: bytes, generated_at: datetime) -> str:
        timestamp = generated_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        key = f"{self.prefix}/{generated_at.astimezone(timezone.utc):%Y/%m/%d}/articles-{timestamp}.json"
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
                ServerSideEncryption="AES256",
            )
        except Exception as error:
            raise ObjectStorageError("S3 snapshot upload failed") from error
        return key
