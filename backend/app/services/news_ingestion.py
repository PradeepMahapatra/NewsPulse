import hashlib
import logging
import os
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


logger = logging.getLogger(__name__)


class NewsIngestionError(Exception):
    """Base error for failures while retrieving or normalizing news."""


class NewsConfigurationError(NewsIngestionError):
    """Raised when the Currents API is not configured."""


class NewsAuthenticationError(NewsIngestionError):
    """Raised when Currents rejects the configured credentials."""


class NewsRateLimitError(NewsIngestionError):
    """Raised when Currents rate-limits the request."""


class NewsArticle(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    title: str
    description: str | None = None
    url: str
    source: str | None = None
    published_at: datetime | None = None
    language: str | None = None
    country: str | None = None
    category: str | None = None
    author: str | None = None
    image: str | None = None

    @field_validator("title", "url", mode="before")
    @classmethod
    def require_non_empty_text(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("article field must be a non-empty string")
        return value.strip()


def _optional_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _published_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def normalize_article(raw_article: Any) -> NewsArticle | None:
    if not isinstance(raw_article, dict):
        return None

    category = raw_article.get("category")
    if isinstance(category, list):
        category = ", ".join(item for item in category if isinstance(item, str))

    normalized = {
        "id": _optional_text(raw_article.get("id")),
        "title": raw_article.get("title"),
        "description": _optional_text(raw_article.get("description")),
        "url": raw_article.get("url"),
        "source": _optional_text(raw_article.get("source")),
        "published_at": _published_at(raw_article.get("published")),
        "language": _optional_text(raw_article.get("language")),
        "country": _optional_text(raw_article.get("country")),
        "category": _optional_text(category),
        "author": _optional_text(raw_article.get("author")),
        "image": _optional_text(raw_article.get("image")),
    }

    try:
        return NewsArticle.model_validate(normalized)
    except ValidationError:
        logger.warning("Skipping malformed article record")
        return None


class CurrentsAPIClient:
    """Small client for the Currents API v1 latest-news endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        load_dotenv()
        self._api_key = api_key if api_key is not None else os.getenv("CURRENTS_API_KEY")
        self._timeout = timeout
        self._http_client = http_client

    def fetch_latest_news(self, limit: int = 10) -> list[NewsArticle]:
        if not self._api_key:
            raise NewsConfigurationError("CURRENTS_API_KEY is not configured")
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")

        client = self._http_client or httpx.Client(timeout=self._timeout)
        close_client = self._http_client is None
        try:
            response = client.get(
                "https://api.currentsapi.services/v1/latest-news",
                headers={"Authorization": self._api_key},
                params={"page_size": limit},
            )
        except httpx.TimeoutException as error:
            raise NewsIngestionError("Currents API request timed out") from error
        except httpx.HTTPError as error:
            raise NewsIngestionError("Currents API request failed") from error
        finally:
            if close_client:
                client.close()

        if response.status_code in (401, 403):
            raise NewsAuthenticationError("Currents API authentication failed")
        if response.status_code == 429:
            raise NewsRateLimitError("Currents API rate limit reached")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise NewsIngestionError("Currents API returned an HTTP error") from error

        try:
            payload = response.json()
        except ValueError as error:
            raise NewsIngestionError("Currents API returned invalid JSON") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("news"), list):
            raise NewsIngestionError("Currents API returned an invalid response")

        return [
            article
            for raw_article in payload["news"]
            if (article := normalize_article(raw_article)) is not None
        ]


class ArticleDeduplicator:
    """Tracks article identifiers for one in-memory ingestion run."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def unique_articles(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        unique: list[NewsArticle] = []
        for article in articles:
            key = article.id or article.url or hashlib.sha256(article.title.encode()).hexdigest()
            if key in self._seen:
                logger.warning("Skipping duplicate article")
                continue
            self._seen.add(key)
            unique.append(article)
        return unique


class NewsIngestionService:
    def __init__(self, client: CurrentsAPIClient | None = None) -> None:
        self._client = client or CurrentsAPIClient()
        self._deduplicator = ArticleDeduplicator()

    def fetch_latest_news(self, limit: int = 10) -> list[NewsArticle]:
        return self._deduplicator.unique_articles(self._client.fetch_latest_news(limit))