import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLE_REPOS_DIR = BASE_DIR / "sample_repos"
WORKSPACES_DIR = BASE_DIR / "backend" / "workspaces"


class Settings(BaseSettings):
    APP_NAME: str = "AI Software Engineering Agent"
    APP_VERSION: str = "1.0.0"

    # Database (PostgreSQL + pgvector primary, automatic fallback to SQLite for local offline dev)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/swe_agent",
    )
    SQLITE_FALLBACK_URL: str = f"sqlite:///{(BASE_DIR / 'backend' / 'swe_agent_local.db').as_posix()}"

    # LLM Settings (Gemini API / OpenAI API / Offline AST Fallback)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")  # auto | gemini | openai | mock
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDING_DIMENSION: int = 64

    # GitHub Integration
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    # Self-healing agent loop configuration
    MAX_TEST_ITERATIONS: int = int(os.getenv("MAX_TEST_ITERATIONS", "3"))

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)

