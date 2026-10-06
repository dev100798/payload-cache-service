import hashlib
import json
from uuid import UUID

from sqlmodel import Session, select

from app.models import Payload, TransformerCache
from app.schemas import PayloadCreateRequest
from app.services.transformer import transform_text


def serialize_request(request: PayloadCreateRequest) -> str:
    return json.dumps(
        {"list_1": request.list_1, "list_2": request.list_2},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def hash_request(request_json: str) -> str:
    return hashlib.sha256(request_json.encode("utf-8")).hexdigest()


def create_payload(session: Session, request: PayloadCreateRequest) -> UUID:
    request_json = serialize_request(request)
    request_hash = hash_request(request_json)

    existing_payload = session.exec(
        select(Payload).where(Payload.request_hash == request_hash)
    ).first()
    if existing_payload is not None:
        return existing_payload.id

    transformed_by_source = get_transformed_values(
        session,
        [*request.list_1, *request.list_2],
    )
    output = build_output(request, transformed_by_source)

    payload = Payload(
        request_hash=request_hash,
        request_json=request_json,
        output=output,
    )
    session.add(payload)
    session.commit()
    session.refresh(payload)

    return payload.id


def get_payload(session: Session, payload_id: UUID) -> Payload | None:
    return session.get(Payload, payload_id)


def get_transformed_values(
    session: Session,
    source_values: list[str],
) -> dict[str, str]:
    unique_sources = list(dict.fromkeys(source_values))
    cached_by_source: dict[str, str] = {}

    if unique_sources:
        cached_rows = session.exec(
            select(TransformerCache).where(
                TransformerCache.source_text.in_(unique_sources)
            )
        ).all()
        cached_by_source = {
            row.source_text: row.transformed_text for row in cached_rows
        }

    missing_sources = [
        source for source in unique_sources if source not in cached_by_source
    ]
    new_rows = []
    for source in missing_sources:
        transformed = transform_text(source)
        cached_by_source[source] = transformed
        new_rows.append(
            TransformerCache(source_text=source, transformed_text=transformed)
        )

    session.add_all(new_rows)
    return cached_by_source


def build_output(
    request: PayloadCreateRequest,
    transformed_by_source: dict[str, str],
) -> str:
    interleaved: list[str] = []
    for left, right in zip(request.list_1, request.list_2, strict=True):
        interleaved.append(transformed_by_source[left])
        interleaved.append(transformed_by_source[right])

    return ", ".join(interleaved)
