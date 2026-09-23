from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.database.config import get_database_url
from backend.app.database.models import Base


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    engine = create_engine(database_url or get_database_url(), pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database(database_url: str | None = None) -> None:
    engine = create_engine(database_url or get_database_url(), pool_pre_ping=True)
    Base.metadata.create_all(engine)


def get_db() -> Generator[Session, None, None]:
    session_factory = create_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()