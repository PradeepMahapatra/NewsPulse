from fastapi import FastAPI, HTTPException

from backend.app.database.config import DatabaseConfigurationError
from backend.app.database.repository import ArticleRepository
from backend.app.services.news_ingestion import (
    NewsIngestionError,
    NewsIngestionService,
)


app = FastAPI(title="NewsPulse API")


def get_ingestion_service() -> NewsIngestionService:
    return NewsIngestionService()


def get_article_repository() -> ArticleRepository:
    return ArticleRepository()


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "NewsPulse is running"}


@app.get("/articles/fetch")
def fetch_articles(limit: int = 10) -> dict[str, object]:
    try:
        articles = get_ingestion_service().fetch_latest_news(limit)
    except (NewsIngestionError, DatabaseConfigurationError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"articles": [article.model_dump(mode="json") for article in articles]}


@app.get("/articles")
def list_articles(limit: int = 100) -> dict[str, object]:
    try:
        articles = get_article_repository().list_articles(limit)
    except (DatabaseConfigurationError, ValueError) as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return {"articles": [
        {
            "id": article.currents_id,
            "title": article.title,
            "description": article.description,
            "url": article.url,
            "source": article.source,
            "author": article.author,
            "published_at": article.published_at,
            "language": article.language,
            "country": article.country,
            "category": article.category,
            "image": article.image,
            "created_at": article.created_at,
        }
        for article in articles
    ]}