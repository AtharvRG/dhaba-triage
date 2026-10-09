from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    triage_mode: str = "fixture"          # "fixture" | "live"
    mistral_api_key: str = ""
    model_name: str = "zai-glm-5-3"

    class Config:
        env_file = ".env"


settings = Settings()