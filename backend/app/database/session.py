from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database.config import get_database_url
from backend.app.database.models import Base


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    engine = create_engine(database_url or get_database_url(), pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database(database_url: str | None = None) -> None:
    engine = create_engine(database_url or get_database_url(), pool_pre_ping=True)
    Base.metadata.create_all(engine)
    column_types = {
        "language_detected": "VARCHAR(16)",
        "analysis_text": "TEXT",
        "sentiment_label": "VARCHAR(16)",
        "sentiment_confidence": "DOUBLE PRECISION",
        "analyzed_at": "TIMESTAMP WITH TIME ZONE",
    }
    with engine.begin() as connection:
        existing_columns = {column["name"] for column in inspect(connection).get_columns("articles")}
        for column_name, column_type in column_types.items():
            if column_name not in existing_columns:
                if engine.dialect.name == "sqlite":
                    column_type = {
                        "sentiment_confidence": "FLOAT",
                        "analyzed_at": "DATETIME",
                    }.get(column_name, column_type)
                connection.execute(
                    text(f"ALTER TABLE articles ADD COLUMN {column_name} {column_type}")
                )


def get_db() -> Generator[Session, None, None]:
    session_factory = create_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()