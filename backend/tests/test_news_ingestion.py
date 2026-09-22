import httpx
import pytest

from backend.app.services.news_ingestion import (
    CurrentsAPIClient,
    NewsAuthenticationError,
    NewsConfigurationError,
    NewsIngestionError,
    NewsIngestionService,
    normalize_article,
)


def make_client(payload: object, status_code: int = 200) -> CurrentsAPIClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "test-key"
        return httpx.Response(status_code, json=payload)

    return CurrentsAPIClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_successful_article_retrieval() -> None:
    client = make_client({"news": [{"id": "1", "title": "Headline", "url": "https://example.com/1"}]})

    articles = client.fetch_latest_news()

    assert articles[0].title == "Headline"
    assert articles[0].url == "https://example.com/1"


def test_empty_response_returns_empty_list() -> None:
    assert make_client({"news": []}).fetch_latest_news() == []


def test_invalid_api_response_raises_error() -> None:
    with pytest.raises(NewsIngestionError):
        make_client({"unexpected": []}).fetch_latest_news()


def test_missing_optional_fields_are_safe_and_missing_url_is_skipped() -> None:
    assert normalize_article({"title": "No URL"}) is None
    article = normalize_article({"title": "Headline", "url": "https://example.com"})
    assert article is not None
    assert article.description is None
    assert article.published_at is None


def test_duplicate_detection_uses_article_url() -> None:
    payload = {"news": [{"title": "Headline", "url": "https://example.com"}]}
    service = NewsIngestionService(make_client(payload))

    assert len(service.fetch_latest_news()) == 1
    assert service.fetch_latest_news() == []


def test_network_failure_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = CurrentsAPIClient(
        api_key="test-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(NewsIngestionError, match="request failed"):
        client.fetch_latest_news()


def test_authentication_failure_is_handled() -> None:
    with pytest.raises(NewsAuthenticationError):
        make_client({"message": "unauthorized"}, status_code=401).fetch_latest_news()


def test_missing_api_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CURRENTS_API_KEY", raising=False)
    with pytest.raises(NewsConfigurationError):
        CurrentsAPIClient(api_key="").fetch_latest_news()