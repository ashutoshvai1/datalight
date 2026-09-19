from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://datalight:datalight@localhost:5432/datalight"
    data_path: Path = Path("/data/input.csv")
    initial_rows: int = Field(default=500, ge=32, le=10000)
    batch_rows: int = Field(default=100, ge=32, le=10000)
    batch_interval: float = Field(default=1, ge=0, le=60)
    deviation_threshold: float = Field(default=6, gt=0, le=100)
    llm_enabled: bool = False
    llm_endpoint: str = (
        "https://containers.datacrunch.io/data-sovereignty-mistral-large-3/v1/chat/completions"
    )
    llm_model: str = "mistralai/Mistral-Large-3-675B-Instruct-2512-NVFP4"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout: float = Field(default=30, gt=0, le=120)

    @field_validator("llm_endpoint")
    @classmethod
    def safe_endpoint(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme not in ("http", "https")
            or not url.netloc
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Use an HTTP(S) endpoint without embedded credentials, query, or fragment; put credentials in LLM_API_KEY."
            )
        return value

    @property
    def interpretation_unavailable(self) -> str | None:
        if not self.llm_enabled:
            return "Model interpretation is disabled. Statistical monitoring remains active."
        if not self.llm_model.strip():
            return "Set LLM_MODEL to the provider's exact model identifier."
        if not self.llm_api_key.get_secret_value() and urlsplit(self.llm_endpoint).hostname not in (
            "localhost",
            "127.0.0.1",
            "host.docker.internal",
            "model",
        ):
            return "Set LLM_API_KEY on the backend before using the hosted model."
        return None
