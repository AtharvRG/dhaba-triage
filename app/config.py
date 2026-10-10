from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    triage_mode: str = "fixture"
    mistral_api_key: str = ""
    model_name: str = "zai-glm-5-3"
    db_path: str = "dhaba.db"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()