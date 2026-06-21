from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    vault_path: Path
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_summary_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    summary_language: str = "ko"
    daily_quota: int = 10

    @property
    def articles_path(self) -> Path:
        return self.vault_path / "Area" / "articles"


settings = Settings()
