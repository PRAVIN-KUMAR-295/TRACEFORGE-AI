import json
from typing import Any, List, Optional, Union
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TRACEFORGE AI"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True

    # FalkorDB Graph Database Configuration
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_username: Optional[str] = None
    falkordb_password: Optional[str] = None
    falkordb_ssl: bool = False
    falkordb_graph_name: str = "traceforge_incidents"
    falkordb_timeout: int = 5
    falkordb_read_only: bool = False

    # LLM Configuration (Configurable Provider Interface)
    # Providers: "demo", "openai", "anthropic", "gemini", "groq", "ollama"
    llm_provider: str = "demo"
    llm_api_key: Optional[str] = None
    llm_model: str = "deterministic-reasoning-engine"
    llm_base_url: Optional[str] = None

    # Deterministic Demo Mode
    demo_mode: bool = True

    # Autonomous Tool-Calling Agent Configuration (Track 1: Connected Data Agent)
    agent_mode: bool = False
    max_agent_iterations: int = 5

    # Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, validation_alias=AliasChoices("api_port", "port", "PORT"))
    cors_origins: Union[List[str], str] = ["*"]

    @field_validator("cors_origins", mode="after")
    @classmethod
    def normalize_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return ["*"]
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
