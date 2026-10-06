from collections.abc import Callable

import pytest
from sqlmodel import Session

from app.schemas import PayloadCreateRequest
from app.services import payload as payload_service


@pytest.fixture()
def transformer_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def fake_transform(value: str) -> str:
        calls.append(value)
        return value.upper()

    monkeypatch.setattr(payload_service, "transform_text", fake_transform)
    return calls


@pytest.fixture()
def make_request() -> Callable[[list[str], list[str]], PayloadCreateRequest]:
    def factory(list_1: list[str], list_2: list[str]) -> PayloadCreateRequest:
        return PayloadCreateRequest(list_1=list_1, list_2=list_2)

    return factory


def test_new_values_are_transformed_once_each(
    db_session: Session,
    make_request: Callable[[list[str], list[str]], PayloadCreateRequest],
    transformer_calls: list[str],
) -> None:
    payload_service.create_payload(db_session, make_request(["hello"], ["world"]))

    assert transformer_calls == ["hello", "world"]


def test_partial_cache_reuse_transforms_only_missing_values(
    db_session: Session,
    make_request: Callable[[list[str], list[str]], PayloadCreateRequest],
    transformer_calls: list[str],
) -> None:
    payload_service.create_payload(db_session, make_request(["hello"], ["world"]))
    transformer_calls.clear()

    payload_service.create_payload(db_session, make_request(["hello"], ["new"]))

    assert transformer_calls == ["new"]


def test_duplicate_strings_inside_one_request_are_transformed_once(
    db_session: Session,
    make_request: Callable[[list[str], list[str]], PayloadCreateRequest],
    transformer_calls: list[str],
) -> None:
    payload_service.create_payload(
        db_session,
        make_request(["hello", "hello"], ["hello", "world"]),
    )

    assert transformer_calls == ["hello", "world"]


def test_complete_payload_reuse_skips_transformer(
    db_session: Session,
    make_request: Callable[[list[str], list[str]], PayloadCreateRequest],
    transformer_calls: list[str],
) -> None:
    request = make_request(["hello"], ["world"])
    first_payload_id = payload_service.create_payload(db_session, request)
    transformer_calls.clear()

    second_payload_id = payload_service.create_payload(db_session, request)

    assert second_payload_id == first_payload_id
    assert transformer_calls == []


def test_output_preserves_order_and_interleaves_values(
    db_session: Session,
    make_request: Callable[[list[str], list[str]], PayloadCreateRequest],
    transformer_calls: list[str],
) -> None:
    payload_id = payload_service.create_payload(
        db_session,
        make_request(["a", "b", "c"], ["x", "y", "z"]),
    )

    payload = payload_service.get_payload(db_session, payload_id)

    assert transformer_calls == ["a", "b", "c", "x", "y", "z"]
    assert payload is not None
    assert payload.output == "A, X, B, Y, C, Z"


def test_payload_identity_includes_ordering(
    db_session: Session,
    make_request: Callable[[list[str], list[str]], PayloadCreateRequest],
    transformer_calls: list[str],
) -> None:
    first_payload_id = payload_service.create_payload(
        db_session,
        make_request(["a", "b"], ["x", "y"]),
    )
    second_payload_id = payload_service.create_payload(
        db_session,
        make_request(["b", "a"], ["x", "y"]),
    )

    assert first_payload_id != second_payload_id


def test_payload_identity_includes_list_membership(
    db_session: Session,
    make_request: Callable[[list[str], list[str]], PayloadCreateRequest],
    transformer_calls: list[str],
) -> None:
    first_payload_id = payload_service.create_payload(
        db_session,
        make_request(["a", "b"], ["x", "y"]),
    )
    second_payload_id = payload_service.create_payload(
        db_session,
        make_request(["x", "y"], ["a", "b"]),
    )

    assert first_payload_id != second_payload_id
