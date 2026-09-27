from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SnapshotResponse(BaseModel):
    status: str
    bucket: str
    key: str
    article_count: int = Field(ge=0)
    generated_at: datetime


class SnapshotPayload(BaseModel):
    snapshot_type: Literal["articles"]
    articles: list[dict[str, object]]
