import logging
from datetime import datetime, timezone
from typing import Any

from backend.app.database.repository import ArticleRepository
from backend.app.services.nlp_preprocessing import build_analysis_text, detect_language
from backend.app.services.sentiment import SentimentAnalyzer


logger = logging.getLogger(__name__)
_shared_analyzer: Any = None


def get_shared_analyzer() -> Any:
    global _shared_analyzer
    if _shared_analyzer is None:
        _shared_analyzer = SentimentAnalyzer()
    return _shared_analyzer


class NLPService:
    def __init__(self, repository: ArticleRepository, analyzer: Any = None) -> None:
        self._repository = repository
        self._analyzer = analyzer or get_shared_analyzer()

    def analyze_articles(self, limit: int = 100) -> dict[str, int]:
        articles = self._repository.list_unanalyzed_articles(limit)
        processed = 0
        failed = 0
        for article in articles:
            text = build_analysis_text(article.title, article.description)
            if not text:
                failed += 1
                continue
            try:
                language = detect_language(text, article.language)
                sentiment = self._analyzer.analyze(text)
                self._repository.update_analysis(
                    article.id,
                    language_detected=language,
                    analysis_text=text,
                    sentiment_label=sentiment.label,
                    sentiment_confidence=sentiment.confidence,
                    analyzed_at=datetime.now(timezone.utc),
                )
                processed += 1
            except Exception:
                failed += 1
                logger.exception("Article NLP analysis failed", extra={"article_id": article.id})
        return {"processed": processed, "skipped": 0, "failed": failed}