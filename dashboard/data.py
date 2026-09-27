from collections import Counter
from typing import Any


SENTIMENTS = ("positive", "neutral", "negative")


def valid_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [article for article in articles if isinstance(article.get("title"), str)]


def filter_articles(
    articles: list[dict[str, Any]],
    *,
    sentiment: str | None = None,
    language: str | None = None,
    country: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    def matches(article: dict[str, Any]) -> bool:
        return all(
            value in (None, "All") or str(article.get(field) or "") == value
            for field, value in (
                ("sentiment_label", sentiment),
                ("language", language),
                ("country", country),
                ("category", category),
            )
        )

    return [article for article in valid_articles(articles) if matches(article)]


def choices(articles: list[dict[str, Any]], field: str) -> list[str]:
    return sorted({str(article[field]) for article in articles if article.get(field)})


def sentiment_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(article.get("sentiment_label") for article in valid_articles(articles))
    return {sentiment: counts.get(sentiment, 0) for sentiment in SENTIMENTS}


def language_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        article.get("language_detected") or article.get("language") or "Unknown"
        for article in valid_articles(articles)
    )
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def country_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(article["country"]).upper()
        for article in valid_articles(articles)
        if article.get("country")
    )
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def analyzed_count(articles: list[dict[str, Any]]) -> int:
    return sum(1 for article in valid_articles(articles) if article.get("analyzed_at"))


def article_table_rows(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Title": article.get("title", "Untitled"),
            "Source": article.get("source") or "Unknown",
            "Published": article.get("published_at") or "-",
            "Country": article.get("country") or "-",
            "Language": article.get("language_detected") or article.get("language") or "-",
            "Sentiment": article.get("sentiment_label") or "-",
            "Confidence": article.get("sentiment_confidence"),
            "URL": article.get("url") or "",
        }
        for article in valid_articles(articles)
    ]
