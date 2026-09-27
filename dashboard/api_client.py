from dataclasses import dataclass
import os
from typing import Any

import httpx


class APIClientError(RuntimeError):
    """Raised when the dashboard cannot use the FastAPI response."""


@dataclass(frozen=True)
class APIClient:
    base_url: str = "http://127.0.0.1:8000"
    timeout: float = 120.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    @classmethod
    def from_environment(cls) -> "APIClient":
        return cls(base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def list_articles(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        sentiment: str | None = None,
        language: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            "limit": limit,
            "offset": offset,
            "sentiment": sentiment,
            "language": language,
            "category": category,
        }
        payload = self._request("GET", "/articles", params=params)
        articles = payload.get("articles")
        if not isinstance(articles, list):
            raise APIClientError("The API returned an invalid article response")
        return [article for article in articles if isinstance(article, dict)]

    def get_article(self, article_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/articles/{article_id}")
        if not isinstance(payload, dict):
            raise APIClientError("The API returned an invalid article response")
        return payload

    def fetch_articles(self, limit: int = 10) -> dict[str, int]:
        return self._operation("POST", "/articles/fetch", params={"limit": limit})

    def analyze_articles(self, limit: int = 100) -> dict[str, int]:
        return self._operation("POST", "/articles/analyze", params={"limit": limit})

    def _operation(
        self, method: str, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, int]:
        payload = self._request(method, path, params=params)
        if not isinstance(payload, dict) or not all(
            isinstance(value, int) for value in payload.values()
        ):
            raise APIClientError("The API returned an invalid operation response")
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                params={key: value for key, value in (params or {}).items() if value not in (None, "")},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise APIClientError("The NewsPulse API timed out") from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                message = "The requested article was not found"
            else:
                message = f"The NewsPulse API returned HTTP {error.response.status_code}"
            raise APIClientError(message) from error
        except httpx.HTTPError as error:
            raise APIClientError("The NewsPulse API is unavailable") from error
        try:
            payload = response.json()
        except ValueError as error:
            raise APIClientError("The NewsPulse API returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise APIClientError("The NewsPulse API returned an invalid response")
        return payload
