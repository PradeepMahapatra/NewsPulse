import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _validate_event(event: Any) -> list[dict[str, Any]]:
    if not isinstance(event, dict) or event.get("snapshot_type") != "articles":
        raise ValueError("snapshot_type must be articles")
    articles = event.get("articles")
    if not isinstance(articles, list) or not all(isinstance(article, dict) for article in articles):
        raise ValueError("articles must be a list of objects")
    return articles


def handler(event: Any, context: Any) -> dict[str, Any]:
    logger.info("NewsPulse snapshot invocation started")
    try:
        articles = _validate_event(event)
        bucket = os.environ["S3_BUCKET_NAME"]
        region = os.getenv("AWS_REGION", "ap-south-1")
        generated_at = datetime.now(timezone.utc)
        timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
        key = f"newspulse/snapshots/{generated_at:%Y/%m/%d}/articles-{timestamp}.json"
        document = {
            "generated_at": generated_at.isoformat(),
            "article_count": len(articles),
            "snapshot_type": "articles",
            "articles": articles,
        }
        body = json.dumps(document, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        boto3.client("s3", region_name=region).put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        logger.info("NewsPulse snapshot upload succeeded: article_count=%d key=%s", len(articles), key)
        return {"status": "success", "bucket": bucket, "key": key, "article_count": len(articles)}
    except (KeyError, TypeError, ValueError):
        logger.warning("NewsPulse snapshot payload validation failed")
        return {"status": "error", "message": "Invalid snapshot payload"}
    except Exception:
        logger.exception("NewsPulse snapshot upload failed")
        return {"status": "error", "message": "Snapshot storage is unavailable"}
