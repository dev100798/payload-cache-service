from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class TransformerCache(SQLModel, table=True):
    __tablename__ = "transformer_cache"
    __table_args__ = (
        UniqueConstraint("source_text", name="uq_transformer_cache_source_text"),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_text: str = Field(nullable=False)
    transformed_text: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Payload(SQLModel, table=True):
    __tablename__ = "payload"
    __table_args__ = (UniqueConstraint("request_hash", name="uq_payload_request_hash"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    request_hash: str = Field(nullable=False)
    request_json: str = Field(nullable=False)
    output: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
