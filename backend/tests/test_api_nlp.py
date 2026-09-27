from backend.app import main
from backend.app.database.models import ArticleRecord


def test_articles_endpoint_exposes_nlp_fields(monkeypatch) -> None:
    article = ArticleRecord(
        currents_id="1",
        title="Headline",
        url="https://example.com",
        sentiment_label="positive",
        sentiment_confidence=0.9,
    )

    class FakeRepository:
        def list_articles(self, limit: int):
            return [article]

    monkeypatch.setattr(main, "get_article_repository", lambda: FakeRepository())

    response = main.list_articles()

    assert response["articles"][0]["sentiment_label"] == "positive"
    assert response["articles"][0]["sentiment_confidence"] == 0.9


def test_analyze_endpoint_returns_summary(monkeypatch) -> None:
    class FakeNLPService:
        def analyze_articles(self, limit: int):
            return {"processed": 1, "skipped": 0, "failed": 0}

    monkeypatch.setattr(main, "get_nlp_service", lambda: FakeNLPService())

    assert main.analyze_articles() == {"processed": 1, "skipped": 0, "failed": 0}