from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://route_optimizer:change_me@localhost:5432/route_optimizer"

    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"

    jwt_secret_key: str = "change_me_to_a_long_random_string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    osrm_base_url: str = "http://localhost:5001"
    photon_base_url: str = "https://photon.komoot.io"

    # Origins allowed to call the API from a browser (the React dev server).
    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
