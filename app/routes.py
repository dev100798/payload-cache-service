from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.schemas import (
    PayloadCreateRequest,
    PayloadCreateResponse,
    PayloadReadResponse,
)
from app.services.payload import create_payload, get_payload

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/payload", response_model=PayloadCreateResponse)
def create_payload_route(
    request: PayloadCreateRequest,
    session: SessionDep,
) -> PayloadCreateResponse:
    payload_id = create_payload(session, request)
    return PayloadCreateResponse(id=payload_id)


@router.get("/payload/{payload_id}", response_model=PayloadReadResponse)
def read_payload_route(
    payload_id: UUID,
    session: SessionDep,
) -> PayloadReadResponse:
    payload = get_payload(session, payload_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Payload not found")

    return PayloadReadResponse(output=payload.output)
