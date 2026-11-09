from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    # An unconfigured AI endpoint must not disable health or existing workflows.
    google_api_key: SecretStr = SecretStr("")
    gemini_model: str = Field(default="gemini-2.5-flash", min_length=1, max_length=100)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


ai_settings = AISettings()
