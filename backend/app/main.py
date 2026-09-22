from fastapi import FastAPI, HTTPException

from backend.app.services.news_ingestion import (
    NewsIngestionError,
    NewsIngestionService,
)


app = FastAPI(title="NewsPulse API")


def get_ingestion_service() -> NewsIngestionService:
    return NewsIngestionService()


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "NewsPulse is running"}


@app.get("/articles/fetch")
def fetch_articles(limit: int = 10) -> dict[str, object]:
    try:
        articles = get_ingestion_service().fetch_latest_news(limit)
    except NewsIngestionError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {"articles": [article.model_dump(mode="json") for article in articles]}