from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    vault_path: Path
    openrouter_api_key: str = ""
    # 앞에서부터 시도, 429/빈응답이면 다음 모델로 폴백
    openrouter_models: str = "z-ai/glm-5.2:free,nvidia/nemotron-3-super-120b-a12b:free"
    summary_language: str = "ko"
    daily_quota: int = 10

    @property
    def articles_path(self) -> Path:
        return self.vault_path / "Area" / "articles"

    @property
    def model_chain(self) -> list[str]:
        return [m.strip() for m in self.openrouter_models.split(",") if m.strip()]


settings = Settings()
