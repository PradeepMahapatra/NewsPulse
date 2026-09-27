from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import main
from backend.app.database.models import Base
from backend.app.database.repository import ArticleRepository
from backend.app.services.article_service import ArticleService
from backend.app.services.news_ingestion import CurrentsAPIClient, NewsArticle
from backend.app.services.news_ingestion import NewsIngestionService
from backend.app.services.nlp_service import NLPService


@pytest.fixture
def repository() -> ArticleRepository:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return ArticleRepository(sessionmaker(bind=engine, expire_on_commit=False))


@pytest.fixture
def client(repository: ArticleRepository) -> TestClient:
    class FakeClient:
        def fetch_latest_news(self, limit: int = 10) -> list[NewsArticle]:
            return [
                NewsArticle(
                    id="fetched-1",
                    title="Fetched article",
                    url="https://example.com/fetched",
                )
            ][:limit]

    class FakeAnalyzer:
        def analyze(self, text: str):
            return type("Result", (), {"label": "positive", "confidence": 0.91})()

    ingestion = NewsIngestionService(FakeClient(), repository)
    nlp = NLPService(repository, FakeAnalyzer())
    service = ArticleService(repository, ingestion, nlp)
    main.app.dependency_overrides.clear()
    main.app.dependency_overrides[main.articles.get_article_service] = lambda: service
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def seed_articles(repository: ArticleRepository) -> list:
    return repository.save_articles(
        [
            NewsArticle(
                id="article-1",
                title="First",
                url="https://example.com/1",
                language="en",
                category="general",
            ),
            NewsArticle(
                id="article-2",
                title="Second",
                url="https://example.com/2",
                language="es",
                category="sports",
            ),
            NewsArticle(
                id="article-3",
                title="Third",
                url="https://example.com/3",
                language="en",
                category="general",
            ),
        ]
    )


def test_health_and_openapi(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/articles/{article_id}" in openapi.json()["paths"]


def test_article_list_pagination_filters_and_schema(
    client: TestClient, repository: ArticleRepository
) -> None:
    seed_articles(repository)

    response = client.get("/articles?limit=1&offset=1")
    assert response.status_code == 200
    assert len(response.json()["articles"]) == 1
    assert response.json()["articles"][0]["id"] == "article-2"

    filtered = client.get("/articles?language=en&category=general")
    assert filtered.status_code == 200
    assert [article["id"] for article in filtered.json()["articles"]] == [
        "article-3",
        "article-1",
    ]
    assert set(filtered.json()["articles"][0]) == {
        "id",
        "title",
        "description",
        "url",
        "source",
        "author",
        "published_at",
        "language",
        "country",
        "category",
        "image",
        "language_detected",
        "analysis_text",
        "sentiment_label",
        "sentiment_confidence",
        "analyzed_at",
        "created_at",
    }


def test_article_by_id_and_not_found(
    client: TestClient, repository: ArticleRepository
) -> None:
    seed_articles(repository)

    response = client.get("/articles/article-1")
    assert response.status_code == 200
    assert response.json()["title"] == "First"
    assert client.get("/articles/missing").status_code == 404


def test_invalid_query_parameters_return_422(client: TestClient) -> None:
    assert client.get("/articles?limit=0").status_code == 422
    assert client.get("/articles?limit=201").status_code == 422
    assert client.get("/articles?offset=-1").status_code == 422
    assert client.post("/articles/analyze?limit=0").status_code == 422


def test_fetch_endpoint_returns_actual_counts(client: TestClient) -> None:
    response = client.post("/articles/fetch?limit=1")
    assert response.status_code == 200
    assert response.json() == {"fetched": 1, "inserted": 1, "duplicates": 0}


def test_analyze_endpoint_processes_then_skips(
    client: TestClient, repository: ArticleRepository
) -> None:
    seed_articles(repository)

    first = client.post("/articles/analyze?limit=2")
    assert first.status_code == 200
    assert first.json() == {"processed": 2, "skipped": 0, "failed": 0}

    second = client.post("/articles/analyze?limit=2")
    assert second.status_code == 200
    assert second.json() == {"processed": 1, "skipped": 0, "failed": 0}

    assert client.get("/articles?sentiment=positive").json()["articles"]


def test_database_failure_is_mapped_to_json_500(client: TestClient, monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private database details")

    monkeypatch.setattr(main.articles.ArticleService, "list_articles", fail)
    response = client.get("/articles")
    assert response.status_code == 500
    assert response.json() == {"detail": "Database operation failed"}
    assert "private" not in response.text
