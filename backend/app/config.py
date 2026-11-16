from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Disaster Response API"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/disaster_response"
    jwt_secret_key: str = "change-this-to-a-long-random-secret-before-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Local IndicTrans2 files are deliberately loaded only when an uncached
    # non-English translation is requested; application startup never downloads them.
    indictrans_model_path: str = "models/indictrans2-en-indic-dist-200M"
    indictrans_device: str = "auto"
    # Keep cold UI-bundle translation within the memory budget of modest GPUs.
    indictrans_batch_size: int = 4
    # Greedy decoding is substantially faster for short UI and API messages.  A
    # higher beam count is useful for document translation, but it makes the
    # local API's first request for a locale unnecessarily slow.
    indictrans_num_beams: int = 1

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
