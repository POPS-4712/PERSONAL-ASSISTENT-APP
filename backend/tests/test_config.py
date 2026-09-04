from __future__ import annotations

from app.config import Settings


def test_cors_list_parsing():
    s = Settings(cors_origins="http://a.com, http://b.com ,")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]


def test_cors_origin_regex_optional():
    assert Settings().cors_origin_regex_or_none is None
    s = Settings(cors_origin_regex=r"https://ac-[a-z0-9-]+\.vercel\.app")
    assert s.cors_origin_regex_or_none == r"https://ac-[a-z0-9-]+\.vercel\.app"


def test_runtime_validation_dev_is_lenient():
    s = Settings(environment="development")
    assert s.validate_runtime() == []


def test_runtime_validation_prod_blocks_placeholders():
    s = Settings(
        environment="production",
        jwt_secret="dev-only-insecure-change-me",
        credential_encryption_key="",
        database_url="postgresql+psycopg://u:p@db/ac",
    )
    problems = s.validate_runtime()
    assert any("JWT_SECRET" in p for p in problems)
    assert any("CREDENTIAL_ENCRYPTION_KEY" in p for p in problems)


def test_runtime_validation_prod_passes_with_real_values():
    s = Settings(
        environment="production",
        jwt_secret="x" * 48,
        credential_encryption_key="k" * 44,
        database_url="postgresql+psycopg://u:p@db/ac",
        debug=False,
    )
    assert s.validate_runtime() == []


def _prod(**over) -> Settings:
    base = dict(
        environment="production",
        jwt_secret="x" * 48,
        credential_encryption_key="k" * 44,
        database_url="postgresql+psycopg://u:p@db/ac",
        debug=False,
        cors_origins="https://panel.example.com",
    )
    base.update(over)
    return Settings(**base)


def test_prod_rejects_wildcard_cors():
    """The API sends Allow-Credentials, so '*' can never work. Say so at boot
    instead of letting it look like a mysterious CORS failure in the browser."""
    problems = _prod(cors_origins="*").validate_runtime()
    assert any("AC_CORS_ORIGINS" in p for p in problems)


def test_prod_rejects_a_catch_all_origin_regex():
    problems = _prod(cors_origin_regex=".*").validate_runtime()
    assert any("catch-all" in p for p in problems)


def test_prod_rejects_no_origins_at_all():
    problems = _prod(cors_origins="").validate_runtime()
    assert any("no browser origin" in p for p in problems)


def test_prod_accepts_a_scoped_preview_regex():
    s = _prod(cors_origin_regex=r"^https://ac-[a-z0-9-]+\.vercel\.app$")
    assert s.validate_runtime() == []
