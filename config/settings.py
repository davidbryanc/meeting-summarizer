from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    groq_api_key: str
    gemini_api_key: str
    huggingface_token: str = ""
    app_env: str = "development"
    max_file_size_mb: int = 100
    transcription_provider: str = "groq"
    llm_provider: str = "gemini"
    diarization_enabled: bool = True
    whisperx_for_alignment: bool = True
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"

settings = Settings()