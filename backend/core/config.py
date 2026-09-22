from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):

    APP_NAME: str = "LeadForge Engine"

    VERSION: str = "1.0.0"

    ENVIRONMENT: str = "development"

    DATABASE_URL: str = (
        "sqlite:///./leadforge.db"
    )

    AI_PROVIDER: str = "mock"

    GEMINI_API_KEY: str = ""

    DEEPSEEK_API_KEY: str = ""

    OLLAMA_HOST: str = (
        "http://localhost:11434"
    )

    HUBSPOT_ACCESS_TOKEN: str = ""

    CORS_ORIGINS: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    LOG_LEVEL: str = "INFO"

    RATE_LIMIT_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()