# Payload Cache Service

## Overview

Payload Cache Service is a small FastAPI microservice for generating and caching payloads. It accepts two equal-length lists of strings, transforms each value, interleaves the transformed results, and returns a generated payload by id.

The service caches individual transformer results and reuses existing payload identifiers when the exact same request is submitted again.

## Architecture

- `app/routes.py`: HTTP request/response handling, dependency injection, and HTTP errors.
- `app/services/payload.py`: payload identity, request hashing, transformer-cache lookup, interleaving, and persistence workflow.
- `app/services/transformer.py`: local simulated transformer. It is isolated because the assignment treats this as an external-service boundary.
- `app/database.py`: synchronous SQLModel engine/session setup and table initialization.
- `app/cli.py`: programmatic HTTP client for exercising the API from the command line.

## How caching works

There are two cache levels.

1. Transformer-result cache

   Each unique source string is stored with its transformed value. For a new payload request, the service queries cached values in one batch and calls the transformer only for unseen unique strings. Duplicate strings inside one request are transformed once.

2. Complete payload reuse

   The full request is serialized as deterministic JSON and hashed with SHA-256. The request identity preserves list membership and ordering. If a matching payload already exists, the service returns the existing UUID without querying the transformer cache or transforming anything.

Flow:

```text
POST /payload
  -> serialize request deterministically
  -> SHA-256 request fingerprint
  -> existing payload? return existing id
  -> query transformer cache for unique strings
  -> transform only missing strings
  -> interleave transformed lists
  -> store payload and return id
```

## Project structure

```text
app/
  main.py                  FastAPI application and lifespan startup
  routes.py                POST /payload and GET /payload/{id}
  database.py              SQLModel engine, sessions, init_db()
  models.py                TransformerCache and Payload tables
  schemas.py               Pydantic request/response schemas
  cli.py                   cache-cli command
  services/
    payload.py             Core payload generation and caching logic
    transformer.py         Simulated external transformer
tests/
  conftest.py              Temporary SQLite test DB fixtures
  test_api.py              API integration tests
  test_payload_service.py  Service-layer caching tests
  test_cli.py              CLI behavior tests
Dockerfile
compose.yaml
pyproject.toml
```

## Requirements

- Python 3.12+
- Docker, if running with Docker Compose

## Local setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run the API

```powershell
python -m uvicorn app.main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## API usage

Create a payload:

```http
POST /payload
Content-Type: application/json
```

```json
{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}
```

Representative response:

```json
{
  "id": "05f534a6-1503-452a-96d2-dfef6611d731"
}
```

Read a payload:

```http
GET /payload/{id}
```

Expected output for the sample request:

```json
{
  "output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
}
```

## CLI

Show help:

```powershell
cache-cli --help
```

Supported options:

- `-H`, `--host`: API host, default `http://127.0.0.1:8000`
- `-r`, `--repeat`: number of POST -> GET workflows to run
- `-i`, `--input`: JSON input file, or `-` for stdin
- `-j`, `--json`: JSON input string
- `-o`, `--output`: output file, or `-` for stdout
- `-h`, `--help`: help

The assignment uses `-h` for both host and help. This implementation keeps conventional `-h / --help` behavior and uses `-H / --host` for the server URL.

Direct JSON:

```powershell
cache-cli --json '{""list_1"":[""hello""],""list_2"":[""world""]}'
```

PowerShell can strip inner double quotes when passing JSON to a native Python console script. Doubling the inner quotes, as above, avoids that. File input or stdin also avoids shell quoting issues.

Input file:

```powershell
Set-Content -Path payload.json -Value '{"list_1":["hello"],"list_2":["world"]}' -Encoding UTF8
cache-cli --input payload.json
```

Stdin:

```powershell
Get-Content payload.json -Raw | cache-cli --input -
```

Repeat:

```powershell
cache-cli --input payload.json --repeat 3
```

Output file:

```powershell
cache-cli --input payload.json --output result.json
```

## Tests

```powershell
pytest -v
pytest --cov=app --cov-report=term-missing
```

The tests cover API integration, payload identifier reuse, transformer call minimization, partial cache reuse, duplicate string handling, ordering/interleaving, and CLI behavior.

## Docker

```powershell
docker compose up --build
```

The API is available at:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Stop the service:

```powershell
docker compose down
```

SQLite data is stored at `/app/data/cache.db` inside the container and persisted in the named Docker volume `payload-cache-data`.

## Design decisions

### SQLite

SQLite was chosen because the assignment is self-contained and explicitly allows SQLite or PostgreSQL. SQLModel keeps the database layer compact and relatively portable.

### Transformer

The local transformer uses uppercase because that matches the assignment sample output. It is isolated because it represents an external-service boundary.

### Request fingerprint

SHA-256 over deterministic JSON is used for payload identity. Ordering and list membership are significant.

### Database initialization

For the scope of this take-home, tables are created automatically at startup with SQLModel metadata. For a larger production application, migrations such as Alembic would normally be used.

### Synchronous database access

Synchronous SQLModel sessions keep this small service simple and easy to explain.

### No Redis

The assignment requires persisted cache results in SQLite or PostgreSQL, so adding Redis would introduce unnecessary infrastructure.

## Assumptions and trade-offs

- Empty lists and empty strings are accepted because the assignment does not forbid them.
- The transformer is local and deterministic here, but the service boundary is kept separate to reflect the assignment's external-service simulation.
- SQLite is suitable for this assessment and local Docker run. A larger system might choose PostgreSQL and migrations.
- The service does not implement authentication, rate limiting, or distributed locking because those are outside the assignment scope.
