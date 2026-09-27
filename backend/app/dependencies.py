from fastapi import Depends

from backend.app.database.repository import ArticleRepository
from backend.app.services.article_service import ArticleService
from backend.app.services.news_ingestion import NewsIngestionService
from backend.app.services.nlp_service import NLPService, get_shared_analyzer


def get_article_repository() -> ArticleRepository:
    return ArticleRepository()


def get_ingestion_service(
    repository: ArticleRepository = Depends(get_article_repository),
) -> NewsIngestionService:
    return NewsIngestionService(repository=repository)


def get_nlp_service(
    repository: ArticleRepository = Depends(get_article_repository),
) -> NLPService:
    return NLPService(repository, get_shared_analyzer())


def get_article_service(
    repository: ArticleRepository = Depends(get_article_repository),
    ingestion_service: NewsIngestionService = Depends(get_ingestion_service),
    nlp_service: NLPService = Depends(get_nlp_service),
) -> ArticleService:
    return ArticleService(repository, ingestion_service, nlp_service)
