from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.models import Base
from backend.app.database.repository import ArticleRepository
from backend.app.services.nlp_preprocessing import build_analysis_text, detect_language
from backend.app.services.nlp_service import NLPService
from backend.app.services.sentiment import SentimentAnalyzer
from backend.app.services.news_ingestion import NewsArticle


def make_repository() -> ArticleRepository:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return ArticleRepository(sessionmaker(bind=engine, expire_on_commit=False))


def test_analysis_text_uses_title_and_description() -> None:
    assert build_analysis_text("  Title  ", " Description\nwith spaces ") == "Title Description with spaces"
    assert build_analysis_text("Title", None) == "Title"
    assert build_analysis_text(None, "Description") == "Description"
    assert build_analysis_text(" ", None) == ""


def test_language_metadata_and_fallback_are_normalized() -> None:
    assert detect_language("This is an English sentence.", "EN-us") == "en"
    assert detect_language("यह हिंदी वाक्य है।", None) == "hi"
    assert detect_language("", None) == "unknown"


def test_sentiment_label_and_confidence_are_normalized() -> None:
    def fake_pipeline_factory(*args, **kwargs):
        return lambda text, **options: [[
            {"label": "LABEL_0", "score": 0.87},
            {"label": "LABEL_1", "score": 0.08},
            {"label": "LABEL_2", "score": 0.05},
        ]]

    result = SentimentAnalyzer(fake_pipeline_factory).analyze("A test article")

    assert result.label == "negative"
    assert result.confidence == 0.87


def test_nlp_persists_results_and_skips_analyzed_articles() -> None:
    repository = make_repository()
    repository.save_article(NewsArticle(title="Good news", description="A positive result", url="https://example.com/1"))

    class FakeAnalyzer:
        def analyze(self, text: str):
            return type("Result", (), {"label": "positive", "confidence": 0.91})()

    service = NLPService(repository, FakeAnalyzer())
    assert service.analyze_articles() == {"processed": 1, "skipped": 0, "failed": 0}
    assert service.analyze_articles() == {"processed": 0, "skipped": 0, "failed": 0}
    stored = repository.list_articles()[0]
    assert stored.sentiment_label == "positive"
    assert stored.sentiment_confidence == 0.91
    assert stored.analyzed_at is not None


def test_nlp_batch_continues_after_one_failed_article() -> None:
    repository = make_repository()
    repository.save_articles([
        NewsArticle(title="First", url="https://example.com/1"),
        NewsArticle(title="Second", url="https://example.com/2"),
    ])

    class SometimesFailingAnalyzer:
        def analyze(self, text: str):
            if text == "First":
                raise RuntimeError("model failure")
            return type("Result", (), {"label": "neutral", "confidence": 0.66})()

    result = NLPService(repository, SometimesFailingAnalyzer()).analyze_articles()

    assert result == {"processed": 1, "skipped": 0, "failed": 1}
    stored = {article.title: article for article in repository.list_articles()}
    assert stored["Second"].sentiment_label == "neutral"