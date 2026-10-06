import io
import json
import sys
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from app import cli
from app.schemas import PayloadCreateRequest, PayloadCreateResponse, PayloadReadResponse

VALID_JSON = '{"list_1":["hello"],"list_2":["world"]}'
PAYLOAD_ID = UUID("00000000-0000-4000-8000-000000000001")


@pytest.fixture()
def stub_http(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, object]]:
    calls: list[tuple[str, str, object]] = []

    def fake_post_payload(
        client: httpx.Client,
        base_url: str,
        request: PayloadCreateRequest,
    ) -> PayloadCreateResponse:
        calls.append(("post", base_url, request))
        return PayloadCreateResponse(id=PAYLOAD_ID)

    def fake_get_payload(
        client: httpx.Client,
        base_url: str,
        payload_id: object,
    ) -> PayloadReadResponse:
        calls.append(("get", base_url, payload_id))
        return PayloadReadResponse(output="HELLO, WORLD")

    monkeypatch.setattr(cli, "post_payload", fake_post_payload)
    monkeypatch.setattr(cli, "get_payload", fake_get_payload)
    return calls


def run_cli(
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    stdin: str | None = None,
) -> int:
    monkeypatch.setattr(sys, "argv", ["cache-cli", *args])
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    return cli.main()


def test_json_input_is_parsed_and_validated(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_http: list[tuple[str, str, object]],
) -> None:
    exit_code = run_cli(monkeypatch, ["--json", VALID_JSON])

    output = json.loads(capsys.readouterr().out)
    post_call = stub_http[0]

    assert exit_code == 0
    assert output["iterations"][0]["output"] == "HELLO, WORLD"
    assert post_call[0] == "post"
    assert post_call[1] == "http://127.0.0.1:8000"
    assert isinstance(post_call[2], PayloadCreateRequest)
    assert post_call[2].list_1 == ["hello"]
    assert post_call[2].list_2 == ["world"]


def test_input_file_is_loaded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_http: list[tuple[str, str, object]],
) -> None:
    input_path = tmp_path / "payload.json"
    input_path.write_text(VALID_JSON, encoding="utf-8")

    exit_code = run_cli(monkeypatch, ["--input", str(input_path)])

    json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert len(stub_http) == 2


def test_stdin_is_loaded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_http: list[tuple[str, str, object]],
) -> None:
    exit_code = run_cli(monkeypatch, ["--input", "-"], stdin=VALID_JSON)

    json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert len(stub_http) == 2


def test_output_file_receives_json_without_stdout_duplication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_http: list[tuple[str, str, object]],
) -> None:
    output_path = tmp_path / "result.json"

    exit_code = run_cli(
        monkeypatch,
        ["--json", VALID_JSON, "--output", str(output_path)],
    )
    captured = capsys.readouterr()
    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert captured.out == ""
    assert output["iterations"][0] == {
        "id": str(PAYLOAD_ID),
        "output": "HELLO, WORLD",
    }


def test_repeat_runs_complete_workflow_n_times(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_http: list[tuple[str, str, object]],
) -> None:
    exit_code = run_cli(monkeypatch, ["--json", VALID_JSON, "--repeat", "3"])

    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert len(output["iterations"]) == 3
    assert [call[0] for call in stub_http] == [
        "post",
        "get",
        "post",
        "get",
        "post",
        "get",
    ]


def test_invalid_json_fails_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stub_http: list[tuple[str, str, object]],
) -> None:
    exit_code = run_cli(monkeypatch, ["--json", "{bad json}"])
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "invalid JSON input" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_mutually_exclusive_input_sources_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "payload.json"
    input_path.write_text(VALID_JSON, encoding="utf-8")

    exit_code = run_cli(
        monkeypatch,
        ["--input", str(input_path), "--json", VALID_JSON],
    )
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "supply exactly one of --input or --json" in captured.err
    assert "Traceback" not in captured.err


def test_missing_input_source_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(monkeypatch, [])
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "supply exactly one of --input or --json" in captured.err
    assert "Traceback" not in captured.err


def test_invalid_repeat_fails_validation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(monkeypatch, ["--json", VALID_JSON, "--repeat", "0"])
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "greater than 0" in captured.err
    assert "Traceback" not in captured.err


def test_http_failure_uses_concise_error_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_post_payload(
        client: httpx.Client,
        base_url: str,
        request: PayloadCreateRequest,
    ) -> PayloadCreateResponse:
        raise cli.CliError("HTTP 500 from POST http://127.0.0.1:8000/payload")

    monkeypatch.setattr(cli, "post_payload", fake_post_payload)

    exit_code = run_cli(monkeypatch, ["--json", VALID_JSON])
    captured = capsys.readouterr()

    assert exit_code != 0
    assert "HTTP 500 from POST" in captured.err
    assert "Traceback" not in captured.err


def test_post_payload_converts_request_error_to_cli_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(handler)
    request = PayloadCreateRequest(list_1=["hello"], list_2=["world"])

    with httpx.Client(transport=transport) as client:
        with pytest.raises(cli.CliError, match="request failed"):
            cli.post_payload(client, "http://127.0.0.1:8000", request)
