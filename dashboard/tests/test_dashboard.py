import httpx
import pytest

from dashboard.api_client import APIClient, APIClientError
from dashboard.data import (
    analyzed_count,
    article_table_rows,
    country_counts,
    filter_articles,
    language_counts,
    sentiment_counts,
)


ARTICLES = [
    {
        "id": "1",
        "title": "Positive English",
        "url": "https://example.com/1",
        "language": "en",
        "language_detected": "en",
        "country": "us",
        "category": "technology",
        "sentiment_label": "positive",
        "sentiment_confidence": 0.9,
        "analyzed_at": "2026-09-27T00:00:00Z",
    },
    {
        "id": "2",
        "title": "Spanish News",
        "url": "https://example.com/2",
        "language": "es",
        "language_detected": "es",
        "country": "es",
        "category": "sports",
        "sentiment_label": None,
        "sentiment_confidence": None,
        "analyzed_at": None,
    },
    {
        "id": "3",
        "title": "No Location",
        "url": "https://example.com/3",
        "language": None,
        "language_detected": None,
        "country": None,
        "category": "technology",
        "sentiment_label": "negative",
        "sentiment_confidence": 0.7,
        "analyzed_at": "2026-09-27T00:00:00Z",
    },
]


def test_successful_article_retrieval(monkeypatch) -> None:
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"articles": ARTICLES}

    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: Response())
    assert APIClient("http://api").list_articles() == ARTICLES


def test_api_error_and_timeout_are_user_safe(monkeypatch) -> None:
    def error_request(*args, **kwargs):
        raise httpx.ConnectError("private connection detail")

    monkeypatch.setattr(httpx, "request", error_request)
    with pytest.raises(APIClientError, match="unavailable"):
        APIClient("http://api").health()

    def timeout_request(*args, **kwargs):
        raise httpx.ReadTimeout("private timeout detail")

    monkeypatch.setattr(httpx, "request", timeout_request)
    with pytest.raises(APIClientError, match="timed out"):
        APIClient("http://api").health()


def test_empty_and_invalid_article_response(monkeypatch) -> None:
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"articles": []}

    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: Response())
    assert APIClient("http://api").list_articles() == []

    class InvalidResponse(Response):
        def json(self):
            return {"wrong": []}

    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: InvalidResponse())
    with pytest.raises(APIClientError, match="invalid article"):
        APIClient("http://api").list_articles()


def test_filtering_and_aggregations_handle_missing_values() -> None:
    selected = filter_articles(ARTICLES, category="technology")
    assert [article["id"] for article in selected] == ["1", "3"]
    assert sentiment_counts(ARTICLES) == {"positive": 1, "neutral": 0, "negative": 1}
    assert language_counts(ARTICLES) == {"en": 1, "es": 1, "Unknown": 1}
    assert country_counts(ARTICLES) == {"ES": 1, "US": 1}
    assert analyzed_count(ARTICLES) == 2


def test_table_rows_are_user_facing_only() -> None:
    rows = article_table_rows(ARTICLES)
    assert rows[0]["Title"] == "Positive English"
    assert rows[0]["Confidence"] == 0.9
    assert "id" not in rows[0]
