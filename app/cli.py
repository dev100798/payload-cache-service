import json
import sys
from pathlib import Path
from typing import Self

import httpx
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Field,
    PositiveInt,
    ValidationError,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas import (
    PayloadCreateRequest,
    PayloadCreateResponse,
    PayloadReadResponse,
)


class CliError(Exception):
    pass


class CliSettings(BaseSettings):
    host: AnyHttpUrl = Field(
        default="http://127.0.0.1:8000",
        description="Server base URL",
    )
    repeat: PositiveInt = Field(
        default=1,
        description="Number of POST/GET workflows to run",
    )
    input: str | None = Field(
        default=None,
        description='Input JSON file path, or "-" for stdin',
    )
    json_text: str | None = Field(
        default=None,
        alias="json",
        description="Input JSON string",
    )
    output: str = Field(
        default="-",
        description='Output JSON file path, or "-" for stdout',
    )

    model_config = SettingsConfigDict(
        case_sensitive=True,
        cli_parse_args=True,
        cli_prog_name="cache-cli",
        cli_shortcuts={
            "host": "H",
            "repeat": "r",
            "input": "i",
            "json": "j",
            "output": "o",
        },
    )

    @model_validator(mode="after")
    def validate_input_source(self) -> Self:
        if (self.input is None) == (self.json_text is None):
            raise ValueError("supply exactly one of --input or --json")
        return self


def main() -> int:
    try:
        settings = CliSettings()
        request = load_request(settings)
        result = run_requests(settings, request)
        write_output(result, settings.output)
    except ValidationError as exc:
        print(f"error: {format_validation_error(exc)}", file=sys.stderr)
        return 2
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


def load_request(settings: CliSettings) -> PayloadCreateRequest:
    raw_input = load_raw_input(settings)

    try:
        parsed_input = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        raise CliError(f"invalid JSON input: {exc.msg}") from exc

    try:
        return PayloadCreateRequest.model_validate(parsed_input)
    except ValidationError as exc:
        raise CliError(f"invalid payload: {format_validation_error(exc)}") from exc


def load_raw_input(settings: CliSettings) -> str:
    if settings.json_text is not None:
        return settings.json_text

    if settings.input == "-":
        return sys.stdin.read()

    try:
        return Path(settings.input or "").read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(f"unable to read input file: {exc}") from exc


def run_requests(
    settings: CliSettings,
    request: PayloadCreateRequest,
) -> dict[str, list[dict[str, str]]]:
    base_url = str(settings.host).rstrip("/")
    iterations: list[dict[str, str]] = []

    with httpx.Client(timeout=10.0) as client:
        for _ in range(settings.repeat):
            created_payload = post_payload(client, base_url, request)
            read_payload = get_payload(client, base_url, created_payload.id)
            iterations.append(
                {
                    "id": str(created_payload.id),
                    "output": read_payload.output,
                }
            )

    return {"iterations": iterations}


def post_payload(
    client: httpx.Client,
    base_url: str,
    request: PayloadCreateRequest,
) -> PayloadCreateResponse:
    try:
        response = client.post(f"{base_url}/payload", json=request.model_dump())
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CliError(format_http_error(exc)) from exc
    except httpx.RequestError as exc:
        raise CliError(f"request failed: {exc}") from exc

    return parse_response(response, PayloadCreateResponse)


def get_payload(
    client: httpx.Client,
    base_url: str,
    payload_id: object,
) -> PayloadReadResponse:
    try:
        response = client.get(f"{base_url}/payload/{payload_id}")
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CliError(format_http_error(exc)) from exc
    except httpx.RequestError as exc:
        raise CliError(f"request failed: {exc}") from exc

    return parse_response(response, PayloadReadResponse)


def parse_response[T: BaseModel](response: httpx.Response, model: type[T]) -> T:
    try:
        response_json = response.json()
    except json.JSONDecodeError as exc:
        raise CliError("invalid server response: response body is not JSON") from exc

    try:
        return model.model_validate(response_json)
    except ValidationError as exc:
        raise CliError(
            f"invalid server response: {format_validation_error(exc)}"
        ) from exc


def write_output(result: dict[str, list[dict[str, str]]], output_path: str) -> None:
    output_json = json.dumps(result, ensure_ascii=False, indent=2) + "\n"

    if output_path == "-":
        sys.stdout.write(output_json)
        return

    try:
        Path(output_path).write_text(output_json, encoding="utf-8")
    except OSError as exc:
        raise CliError(f"unable to write output file: {exc}") from exc


def format_http_error(exc: httpx.HTTPStatusError) -> str:
    request = exc.request
    response = exc.response
    return f"HTTP {response.status_code} from {request.method} {request.url}"


def format_validation_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error["loc"])
    message = error["msg"].removeprefix("Value error, ")
    return f"{location}: {message}" if location else message
