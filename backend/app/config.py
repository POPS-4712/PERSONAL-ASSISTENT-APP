"""Application settings, loaded from environment variables.

Every value that matters for a deployment comes from the environment (the web
control plane / installer writes them into `.env`). Nothing here is a secret
literal; placeholders are inert and rejected by `validate_runtime()`.
"""
from __future__ import annotations

import functools
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
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
    # Comma-separated list of allowed browser origins (the frontend).
    cors_origins: str = "http://localhost:3000"
    # Optional regex for allowed origins, used for Vercel preview deployments
    # e.g. r"https://automation-center-[a-z0-9-]+\.vercel\.app". Empty = disabled.
    # Keep this scoped to your own project; never use ".*".
    cors_origin_regex: str = ""

    # --- Database (Automation Center's own DB, separate from n8n's) ---
    database_url: str = "postgresql+psycopg://automation:automation@localhost:5432/automation_center"

    # --- Auth ---
    jwt_secret: str = "dev-only-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14
    # Open registration: the first account always becomes admin. When locked
    # (installer does this after creating the admin), only admins create users.
    allow_open_registration: bool = True
    # Rate limits (slowapi syntax). Auth endpoints get the stricter one.
    rate_limit_auth: str = "10/minute"
    rate_limit_default: str = "120/minute"
    # Comma-separated CIDRs of reverse proxies we trust to set X-Forwarded-For.
    # Empty (default) = the backend is treated as directly exposed and the
    # X-Forwarded-For header is ignored for rate-limiting (it is client-spoofable).
    # Desktop install: leave empty. Behind nginx/Traefik on the same host:
    # "127.0.0.1/32,::1/128". Behind a cloud LB: that LB's egress range.
    trusted_proxies: str = ""
    # Password policy.
    password_min_length: int = 10

    # --- Credential encryption (phase 6). 32 url-safe base64 bytes = Fernet key. ---
    credential_encryption_key: str = ""

    # --- n8n integration ---
    # Also honours the plain N8N_API_URL / N8N_API_KEY names already in .env.
    n8n_base_url: str = Field(
        default="http://n8n:5678",
        validation_alias=AliasChoices("AC_N8N_BASE_URL", "N8N_API_URL", "N8N_URL"),
    )
    n8n_api_key: str = Field(
        default="", validation_alias=AliasChoices("AC_N8N_API_KEY", "N8N_API_KEY")
    )

    # --- Gemini / AI provider ---
    # Also honours the plain GEMINI_API_KEY name already used by the workflows.
    gemini_api_key: str = Field(
        default="", validation_alias=AliasChoices("AC_GEMINI_API_KEY", "GEMINI_API_KEY")
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        validation_alias=AliasChoices("AC_GEMINI_MODEL", "GEMINI_MODEL"),
    )
    # How long a successful live Gemini verification is trusted before the
    # monitor calls the provider again. The monitor loop ticks every few
    # seconds; re-validating a key that often would waste provider quota.
    gemini_verify_ttl_seconds: float = 300.0

    # --- Optional sidecar services ---
    # Empty = not deployed in this environment -> the monitor reports
    # NOT_CONFIGURED instead of OFFLINE. Docker Compose sets this to the
    # in-network hostname; a stand-alone backend deploy leaves it unset.
    #
    # These are only the DEFAULT: `services.service_config` prefers the
    # `service_configs` table, which the web panel writes, so a user can change
    # the endpoint without an env edit or a redeploy.
    playwright_base_url: str = Field(
        default="", validation_alias=AliasChoices("AC_PLAYWRIGHT_BASE_URL", "PLAYWRIGHT_BASE_URL")
    )
    # Deprecated. The `profile` container is a local helper that maintains
    # config/user_profile.json for the n8n Code nodes; it is NOT what the
    # monitor means by PROFILE. Since v0.5 that state is computed from the
    # `profiles` table (see services/profiles.any_complete_profile), because a
    # reachable sidecar said nothing about whether usable profile data existed.
    # Kept so an existing .env with this key still loads.
    profile_base_url: str = ""

    # --- Monitoring ---
    monitor_interval_seconds: float = 5.0
    compose_project: str = "personal-assistant"

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Pin the psycopg (v3) dialect.

        Managed Postgres providers (Render, Neon, Supabase, RDS) hand out a
        driver-less ``postgres://`` / ``postgresql://`` URL. SQLAlchemy would
        then default to psycopg2, which this backend does not ship. Rewrite the
        scheme so ``fromDatabase`` wiring works with no manual edit.
        """
        v = v.strip()
        if v.startswith("postgresql+") or v.startswith("sqlite"):
            return v
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://") :]
        return v

    @property
    def trusted_proxy_networks(self) -> list:
        import ipaddress

        nets = []
        for token in self.trusted_proxies.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                nets.append(ipaddress.ip_network(token, strict=False))
            except ValueError:
                continue
        return nets

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_origin_regex_or_none(self) -> str | None:
        return self.cors_origin_regex.strip() or None

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
