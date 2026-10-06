from uuid import UUID

from fastapi.testclient import TestClient


def sample_payload() -> dict[str, list[str]]:
    return {
        "list_1": ["first string", "second string", "third string"],
        "list_2": ["other string", "another string", "last string"],
    }


def test_create_payload_returns_uuid(client: TestClient) -> None:
    response = client.post("/payload", json=sample_payload())

    assert response.status_code == 200
    UUID(response.json()["id"])


def test_read_payload_returns_generated_output(client: TestClient) -> None:
    create_response = client.post("/payload", json=sample_payload())
    payload_id = create_response.json()["id"]

    response = client.get(f"/payload/{payload_id}")

    assert response.status_code == 200
    assert response.json() == {
        "output": (
            "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, "
            "THIRD STRING, LAST STRING"
        )
    }


def test_posting_same_payload_reuses_identifier(client: TestClient) -> None:
    first_response = client.post("/payload", json=sample_payload())
    second_response = client.post("/payload", json=sample_payload())

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["id"] == second_response.json()["id"]


def test_unknown_payload_returns_404(client: TestClient) -> None:
    payload_id = "00000000-0000-4000-8000-000000000000"

    response = client.get(f"/payload/{payload_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Payload not found"


def test_invalid_uuid_returns_422(client: TestClient) -> None:
    response = client.get("/payload/not-a-uuid")

    assert response.status_code == 422


def test_unequal_list_lengths_return_422(client: TestClient) -> None:
    response = client.post(
        "/payload",
        json={"list_1": ["a", "b"], "list_2": ["x"]},
    )

    assert response.status_code == 422


def test_empty_lists_are_accepted(client: TestClient) -> None:
    create_response = client.post("/payload", json={"list_1": [], "list_2": []})
    payload_id = create_response.json()["id"]

    read_response = client.get(f"/payload/{payload_id}")

    assert create_response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json() == {"output": ""}
