from backend.app import main
from backend.app.services.news_ingestion import NewsArticle, NewsIngestionService


class FakeIngestionService:
    def fetch_latest_news(self, limit: int = 10) -> list[NewsArticle]:
        return [NewsArticle(title="Headline", url="https://example.com")]


def test_fetch_articles_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(main, "get_ingestion_service", lambda: FakeIngestionService())

    response = main.fetch_articles()

    assert response["articles"][0]["title"] == "Headline"