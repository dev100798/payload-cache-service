from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(title="Payload Cache Service")


app = create_app()
