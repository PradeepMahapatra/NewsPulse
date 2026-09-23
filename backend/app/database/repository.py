from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database.session import create_session_factory
from backend.app.database.models import ArticleRecord
from backend.app.services.news_ingestion import NewsArticle


class ArticleRepository:
    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self._session_factory = session_factory or create_session_factory()

    def save_article(self, article: NewsArticle) -> bool:
        return bool(self.save_articles([article]))

    def save_articles(self, articles: Iterable[NewsArticle]) -> list[ArticleRecord]:
        article_list = list(articles)
        if not article_list:
            return []

        with self._session_factory() as session:
            urls = {article.url for article in article_list}
            currents_ids = {article.id for article in article_list if article.id}
            existing = session.scalars(
                select(ArticleRecord).where(
                    (ArticleRecord.url.in_(urls))
                    | (ArticleRecord.currents_id.in_(currents_ids) if currents_ids else False)
                )
            ).all()
            existing_urls = {article.url for article in existing}
            existing_ids = {article.currents_id for article in existing if article.currents_id}
            candidate_urls: set[str] = set()
            candidate_ids: set[str] = set()

            records: list[ArticleRecord] = []
            for article in article_list:
                if article.url in existing_urls or article.url in candidate_urls:
                    continue
                if article.id and (article.id in existing_ids or article.id in candidate_ids):
                    continue
                records.append(
                    ArticleRecord(
                        currents_id=article.id,
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
                    )
                )
                candidate_urls.add(article.url)
                if article.id:
                    candidate_ids.add(article.id)
            session.add_all(records)
            session.commit()
            return records

    def list_articles(self, limit: int = 100) -> list[ArticleRecord]:
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        with self._session_factory() as session:
            return list(
                session.scalars(
                    select(ArticleRecord)
                    .order_by(ArticleRecord.published_at.desc().nullslast(), ArticleRecord.id.desc())
                    .limit(limit)
                )
            )