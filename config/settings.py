from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    groq_api_key: str
    app_env: str = "development"
    max_file_size_mb: int = 100
    transcription_provider: str = "groq"

    class Config:
        env_file = ".env"

settings = Settings()