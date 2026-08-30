"""Application settings, loaded from environment variables.

Every value that matters for a deployment comes from the environment (the web
control plane / installer writes them into `.env`). Nothing here is a secret
literal; placeholders are inert and rejected by `validate_runtime()`.
"""
from __future__ import annotations

import functools
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "staging", "production"]

_PLACEHOLDER_MARKERS = ("CAMBIA", "PEGA_AQUI", "PLACEHOLDER", "CHANGE_ME")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AC_",
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = "development"
    debug: bool = False

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    # Comma-separated list of allowed browser origins (the Next.js frontend).
    cors_origins: str = "http://localhost:3000"

    # --- Database (Automation Center's own DB, separate from n8n's) ---
    database_url: str = "postgresql+psycopg://automation:automation@localhost:5432/automation_center"

    # --- Auth (used from phase 4 on) ---
    jwt_secret: str = "dev-only-insecure-change-me"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14

    # --- Credential encryption (phase 6). 32 url-safe base64 bytes = Fernet key. ---
    credential_encryption_key: str = ""

    # --- n8n integration (phase 7) ---
    n8n_base_url: str = "http://n8n:5678"
    n8n_api_key: str = ""

    # --- Docker socket, for host/service metrics (phase 8) ---
    docker_host: str = "unix:///var/run/docker.sock"
    compose_project: str = "personal-assistant"

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment in ("staging", "production")

    def validate_runtime(self) -> list[str]:
        """Return a list of human-readable problems that block a real deployment.

        Empty list == safe to serve. The installer surfaces these as BLOCKED BY.
        """
        problems: list[str] = []

        def looks_placeholder(value: str) -> bool:
            return (not value) or any(m in value for m in _PLACEHOLDER_MARKERS)

        if self.is_production:
            if looks_placeholder(self.jwt_secret) or self.jwt_secret == "dev-only-insecure-change-me":
                problems.append("AC_JWT_SECRET is unset or a placeholder")
            if len(self.jwt_secret) < 32:
                problems.append("AC_JWT_SECRET must be at least 32 characters")
            if looks_placeholder(self.credential_encryption_key):
                problems.append("AC_CREDENTIAL_ENCRYPTION_KEY is unset (needed to store credentials)")
            if self.debug:
                problems.append("AC_DEBUG must be false in production")
        if looks_placeholder(self.database_url):
            problems.append("AC_DATABASE_URL is unset or a placeholder")
        return problems


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
