from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.app.database.models import Base
from backend.app.database.repository import ArticleRepository
from backend.app.services.news_ingestion import NewsArticle, NewsIngestionService


def make_repository() -> ArticleRepository:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return ArticleRepository(sessionmaker(bind=engine, expire_on_commit=False))


def make_article(article_id: str | None = "currents-1") -> NewsArticle:
    return NewsArticle(
        id=article_id,
        title="Headline",
        description="Description",
        url="https://example.com/article",
        source="Example",
        author="Reporter",
        published_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
        language="en",
        country="us",
        category="general",
        image="https://example.com/image.jpg",
    )


def test_article_table_has_expected_columns() -> None:
    repository = make_repository()
    engine = repository._session_factory.kw["bind"]
    columns = {column["name"] for column in inspect(engine).get_columns("articles")}

    assert {
        "currents_id", "title", "description", "url", "source", "author",
        "published_at", "language", "country", "category", "image", "created_at",
    } <= columns


def test_insert_and_retrieve_article() -> None:
    repository = make_repository()

    inserted = repository.save_article(make_article())
    articles = repository.list_articles()

    assert inserted is True
    assert len(articles) == 1
    assert articles[0].title == "Headline"
    assert articles[0].created_at is not None


def test_duplicate_url_and_currents_id_are_ignored() -> None:
    repository = make_repository()
    article = make_article()

    assert len(repository.save_articles([article, article])) == 1
    assert repository.save_article(article) is False
    assert len(repository.list_articles()) == 1


def test_multiple_articles_and_missing_optional_fields() -> None:
    repository = make_repository()
    first = make_article("currents-1")
    second = NewsArticle(title="Second", url="https://example.com/second")

    assert len(repository.save_articles([first, second])) == 2
    stored = repository.list_articles()

    assert len(stored) == 2
    assert any(article.description is None for article in stored)


def test_ingestion_persists_normalized_articles() -> None:
    repository = make_repository()

    class FakeClient:
        def fetch_latest_news(self, limit: int = 10) -> list[NewsArticle]:
            return [make_article()]

    fetched = NewsIngestionService(FakeClient(), repository=repository).fetch_latest_news()

    assert len(fetched) == 1
    assert len(repository.list_articles()) == 1