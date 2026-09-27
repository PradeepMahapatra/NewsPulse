from backend.app.services.news_ingestion import NewsIngestionService, NewsIngestionResult
from backend.app.services.nlp_service import NLPService
from backend.app.database.repository import ArticleRepository


class ArticleService:
    def __init__(
        self,
        repository: ArticleRepository,
        ingestion_service: NewsIngestionService,
        nlp_service: NLPService,
    ) -> None:
        self._repository = repository
        self._ingestion_service = ingestion_service
        self._nlp_service = nlp_service

    def list_articles(
        self,
        *,
        limit: int,
        offset: int,
        sentiment: str | None = None,
        language: str | None = None,
        category: str | None = None,
    ):
        return self._repository.list_articles(
            limit=limit,
            offset=offset,
            sentiment=sentiment,
            language=language,
            category=category,
        )

    def get_article(self, article_id: str):
        return self._repository.get_article(article_id)

    def fetch_articles(self, limit: int) -> NewsIngestionResult:
        return self._ingestion_service.fetch_latest_news_with_stats(limit)

    def analyze_articles(self, limit: int) -> dict[str, int]:
        return self._nlp_service.analyze_articles(limit)
