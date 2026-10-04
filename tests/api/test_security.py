from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orion_api.config import (
    APISettings,
    APIConfigurationError,
    DEFAULT_ALLOWED_ORIGINS,
    MIN_PRODUCTION_API_KEY_LENGTH,
    get_settings,
)
from orion_api.main import create_app

pytestmark = pytest.mark.integration

PRODUCTION_KEY = "k" * MIN_PRODUCTION_API_KEY_LENGTH
PRODUCTION_ORIGIN = "https://site.example.test"


def production_environment(**overrides):
    environment = {
        "ORION_ENV": "production",
        "ORION_API_KEY": PRODUCTION_KEY,
        "ORION_ALLOWED_ORIGINS": PRODUCTION_ORIGIN,
    }
    environment.update(overrides)
    return environment


def test_development_without_api_key_preserves_local_behavior():
    settings = get_settings(environ={})
    client = TestClient(create_app(settings), raise_server_exceptions=False)

    response = client.get("/api/v1/papers")

    assert settings.environment == "development"
    assert settings.api_key is None
    assert settings.allowed_origins == DEFAULT_ALLOWED_ORIGINS
    assert response.status_code == 200


def test_production_without_api_key_fails_closed(monkeypatch):
    monkeypatch.setenv("ORION_ENV", "production")
    monkeypatch.setenv("ORION_ALLOWED_ORIGINS", PRODUCTION_ORIGIN)
    monkeypatch.delenv("ORION_API_KEY", raising=False)

    with pytest.raises(APIConfigurationError, match="required in production"):
        create_app()


def test_production_with_short_key_fails_without_exposing_value():
    short_secret = "sensitive-short-value"

    with pytest.raises(APIConfigurationError) as error:
        get_settings(
            environ=production_environment(ORION_API_KEY=short_secret)
        )

    assert "at least 32 characters" in str(error.value)
    assert short_secret not in str(error.value)


def test_production_requires_explicit_origins():
    with pytest.raises(APIConfigurationError, match="required in production"):
        get_settings(
            environ=production_environment(ORION_ALLOWED_ORIGINS="")
        )


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.test",
        "http://localhost:3000",
        "https://localhost",
        "http://127.0.0.1:8501",
    ],
)
def test_production_rejects_wildcard_and_local_origins(origin):
    with pytest.raises(APIConfigurationError):
        get_settings(
            environ=production_environment(ORION_ALLOWED_ORIGINS=origin)
        )


def test_production_configuration_starts_and_authenticates():
    settings = get_settings(environ=production_environment())
    client = TestClient(create_app(settings), raise_server_exceptions=False)

    public = client.get("/health")
    incorrect = client.get(
        "/api/v1/papers", headers={"X-Orion-API-Key": "incorrect"}
    )
    correct = client.get(
        "/api/v1/papers", headers={"X-Orion-API-Key": PRODUCTION_KEY}
    )

    assert settings.environment == "production"
    assert public.status_code == 200
    assert incorrect.status_code == 401
    assert incorrect.json() == {"detail": "Valid API key required"}
    assert PRODUCTION_KEY not in incorrect.text
    assert correct.status_code == 200
    assert PRODUCTION_KEY not in correct.text


def test_injected_production_settings_cannot_bypass_validation():
    with pytest.raises(APIConfigurationError, match="required in production"):
        create_app(
            APISettings(
                environment="production",
                api_key=None,
                allowed_origins=(PRODUCTION_ORIGIN,),
            )
        )


def test_security_headers_are_present_and_hsts_is_production_only():
    development = TestClient(create_app(get_settings(environ={})))
    production = TestClient(create_app(get_settings(environ=production_environment())))

    development_health = development.get("/health")
    production_health = production.get("/health")
    production_docs = production.get("/docs")

    for response in (development_health, production_health, production_docs):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in development_health.headers
    assert production_health.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert production_docs.status_code == 200


def test_production_cors_remains_restricted():
    client = TestClient(create_app(get_settings(environ=production_environment())))

    allowed = client.options(
        "/api/v1/papers",
        headers={
            "Origin": PRODUCTION_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Orion-API-Key",
        },
    )
    denied = client.options(
        "/api/v1/papers",
        headers={
            "Origin": "https://untrusted.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == PRODUCTION_ORIGIN
    assert "access-control-allow-origin" not in denied.headers


def test_configuration_errors_are_sanitized():
    secret_key = "private-value-that-must-not-appear"
    secret_database = "postgresql://user:password@private.example/db"
    invalid_origin = "https://user:password@site.example.test"

    with pytest.raises(APIConfigurationError) as error:
        get_settings(
            environ={
                "ORION_ENV": "production",
                "ORION_API_KEY": secret_key,
                "ORION_ALLOWED_ORIGINS": invalid_origin,
                "DATABASE_URL": secret_database,
            }
        )

    message = str(error.value)
    assert secret_key not in message
    assert secret_database not in message
    assert invalid_origin not in message
    assert "password" not in message


def test_workflows_use_minimum_permissions_and_nonpersistent_checkout():
    workflows = sorted(Path(".github/workflows").glob("*.yml"))
    assert workflows

    for workflow in workflows:
        contents = workflow.read_text(encoding="utf-8")
        assert "contents: read" in contents
        assert "contents: write" not in contents
        assert contents.count("persist-credentials: false") == contents.count(
            "uses: actions/checkout@"
        )
        assert "git push" not in contents

    assert 'cron: "0 10 * * *"' in Path(
        ".github/workflows/daily-radar.yml"
    ).read_text(encoding="utf-8")
    assert 'cron: "0 12 * * 5"' in Path(
        ".github/workflows/weekly-radar.yml"
    ).read_text(encoding="utf-8")
    assert 'cron: "17 * * * *"' in Path(
        ".github/workflows/orion-health-monitor.yml"
    ).read_text(encoding="utf-8")


def test_dependabot_covers_supported_ecosystems_weekly():
    contents = Path(".github/dependabot.yml").read_text(encoding="utf-8")

    assert "version: 2" in contents
    for ecosystem in ("pip", "github-actions", "docker"):
        assert f"package-ecosystem: {ecosystem}" in contents
    assert contents.count("interval: weekly") == 3
    assert contents.count("open-pull-requests-limit:") == 3


def test_docker_baseline_runs_non_root_and_excludes_sensitive_files():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "COPY --chown=orion:orion . ." in dockerfile
    assert "USER orion" in dockerfile
    for excluded in (".env", ".streamlit/secrets.toml", "*.db", "tests", ".git"):
        assert excluded in dockerignore
    assert "!.env.example" not in dockerignore
