from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Payload Cache Service"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
