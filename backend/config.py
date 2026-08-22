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
    def data_root(self) -> Path:
        """Vault 안에서 이 앱이 쓰는 유일한 폴더. 경로 리터럴은 여기 한 곳에만 둔다."""
        return self.vault_path / "Resource" / "gudok-manbo"

    @property
    def articles_path(self) -> Path:
        """Feed — 아직 처리하지 않은 Item. 만료 대상."""
        return self.data_root / "articles"

    @property
    def collections_path(self) -> Path:
        """Collection — 사용자가 남기기로 선택한 Item. 만료되지 않는다."""
        return self.data_root / "collections"

    @property
    def model_chain(self) -> list[str]:
        return [m.strip() for m in self.openrouter_models.split(",") if m.strip()]


settings = Settings()
