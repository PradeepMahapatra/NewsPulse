from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from backend.app.dependencies import get_article_service
from backend.app.schemas.articles import (
    AnalysisResponse,
    ArticleListResponse,
    ArticleResponse,
    IngestionResponse,
)
from backend.app.services.article_service import ArticleService
from backend.app.services.news_ingestion import (
    NewsAuthenticationError,
    NewsConfigurationError,
    NewsIngestionError,
    NewsRateLimitError,
)


router = APIRouter(prefix="/articles", tags=["articles"])


def _handle_database_error(error: SQLAlchemyError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database operation failed",
    )


@router.get(
    "",
    response_model=ArticleListResponse,
    summary="List stored articles",
)
def list_articles(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sentiment: str | None = Query(default=None, min_length=1),
    language: str | None = Query(default=None, min_length=1),
    category: str | None = Query(default=None, min_length=1),
    service: ArticleService = Depends(get_article_service),
) -> ArticleListResponse:
    try:
        articles = service.list_articles(
            limit=limit,
            offset=offset,
            sentiment=sentiment,
            language=language,
            category=category,
        )
    except (SQLAlchemyError, ValueError) as error:
        if isinstance(error, SQLAlchemyError):
            raise _handle_database_error(error) from error
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ArticleListResponse(
        articles=[ArticleResponse.from_record(article) for article in articles]
    )


@router.post(
    "/fetch",
    response_model=IngestionResponse,
    summary="Fetch and persist the latest news",
    status_code=status.HTTP_200_OK,
)
def fetch_articles(
    limit: int = Query(default=10, ge=1, le=200),
    service: ArticleService = Depends(get_article_service),
) -> IngestionResponse:
    try:
        result = service.fetch_articles(limit)
    except (NewsAuthenticationError, NewsConfigurationError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except NewsRateLimitError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except NewsIngestionError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise _handle_database_error(error) from error
    return IngestionResponse(
        fetched=result.fetched,
        inserted=result.inserted,
        duplicates=result.duplicates,
    )


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Analyze unprocessed articles",
)
def analyze_articles(
    limit: int = Query(default=100, ge=1, le=200),
    service: ArticleService = Depends(get_article_service),
) -> AnalysisResponse:
    try:
        return AnalysisResponse(**service.analyze_articles(limit))
    except SQLAlchemyError as error:
        raise _handle_database_error(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get(
    "/fetch",
    response_model=ArticleListResponse,
    include_in_schema=False,
)
def fetch_articles_legacy(
    limit: int = Query(default=10, ge=1, le=200),
    service: ArticleService = Depends(get_article_service),
) -> ArticleListResponse:
    try:
        result = service.fetch_articles(limit)
    except NewsIngestionError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return ArticleListResponse(
        articles=[
            ArticleResponse(
                id=article.id,
                title=article.title,
                description=article.description,
                url=article.url,
                source=article.source,
                author=article.author,
                published_at=article.published_at,
                language=article.language,
                country=article.country,
                category=article.category,
                image=article.image,
                language_detected=None,
                analysis_text=None,
                sentiment_label=None,
                sentiment_confidence=None,
                analyzed_at=None,
                created_at=None,
            )
            for article in result.articles
        ]
    )


@router.get(
    "/{article_id}",
    response_model=ArticleResponse,
    summary="Retrieve one article",
)
def get_article(
    article_id: str,
    service: ArticleService = Depends(get_article_service),
) -> ArticleResponse:
    if not article_id.strip():
        raise HTTPException(status_code=422, detail="article_id must not be empty")
    try:
        article = service.get_article(article_id)
    except SQLAlchemyError as error:
        raise _handle_database_error(error) from error
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleResponse.from_record(article)
