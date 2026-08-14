from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 172800  # 48 hours
    allowed_origins: list[str] = ["http://localhost:5173"]
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    skill_match_threshold: float = 0.78

    class Config:
        env_file = ".env"


settings = Settings()
