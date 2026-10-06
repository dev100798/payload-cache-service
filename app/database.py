from collections.abc import Generator
from importlib import import_module

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def init_db() -> None:
    import_module("app.models")
    SQLModel.metadata.create_all(engine)
