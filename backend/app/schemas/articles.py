from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | None
    title: str
    description: str | None
    url: str
    source: str | None
    author: str | None
    published_at: datetime | None
    language: str | None
    country: str | None
    category: str | None
    image: str | None
    language_detected: str | None
    analysis_text: str | None
    sentiment_label: str | None
    sentiment_confidence: float | None
    analyzed_at: datetime | None
    created_at: datetime | None

    @classmethod
    def from_record(cls, article: object) -> "ArticleResponse":
        return cls(
            id=getattr(article, "currents_id", None),
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
            language_detected=article.language_detected,
            analysis_text=article.analysis_text,
            sentiment_label=article.sentiment_label,
            sentiment_confidence=article.sentiment_confidence,
            analyzed_at=article.analyzed_at,
            created_at=article.created_at,
        )


class ArticleListResponse(BaseModel):
    articles: list[ArticleResponse]


class IngestionResponse(BaseModel):
    fetched: int = Field(ge=0)
    inserted: int = Field(ge=0)
    duplicates: int = Field(ge=0)


class AnalysisResponse(BaseModel):
    processed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: str
