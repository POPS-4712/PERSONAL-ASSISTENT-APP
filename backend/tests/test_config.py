from __future__ import annotations

from app.config import Settings


def test_cors_list_parsing():
    s = Settings(cors_origins="http://a.com, http://b.com ,")
    assert s.cors_origin_list == ["http://a.com", "http://b.com"]


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
