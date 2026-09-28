from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from orion_api.config import (
    APIConfigurationError,
    APISettings,
    DEFAULT_RATE_LIMIT_READ_PER_MINUTE,
    DEFAULT_RATE_LIMIT_SEARCH_PER_MINUTE,
    DEFAULT_RATE_LIMIT_WRITE_PER_MINUTE,
    MAX_RATE_LIMIT_PER_MINUTE,
    get_settings,
)
from orion_api.main import create_app
from orion_api.rate_limit import (
    CredentialSlot,
    InMemoryRateLimiter,
    RateLimitCategory,
    RateLimitExceeded,
)
from orion_api.services import research_service


pytestmark = pytest.mark.integration

PRIMARY = "p" * 32
SECONDARY = "s" * 32
ORIGIN = "https://site.example.test"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _settings(**overrides) -> APISettings:
    values = {
        "allowed_origins": (ORIGIN,),
        "api_key": PRIMARY,
        "api_key_secondary": SECONDARY,
        "environment": "production",
        "rate_limit_read_per_minute": 2,
        "rate_limit_write_per_minute": 2,
        "rate_limit_search_per_minute": 2,
    }
    values.update(overrides)
    return APISettings(**values)


def _headers(key: str) -> dict[str, str]:
    return {"X-Orion-API-Key": key}


def test_primary_and_secondary_authenticate_without_revealing_slot():
    client = TestClient(create_app(_settings()), raise_server_exceptions=False)

    primary = client.get("/api/v1/sources", headers=_headers(PRIMARY))
    secondary = client.get("/api/v1/sources", headers=_headers(SECONDARY))

    assert primary.status_code == 200
    assert secondary.status_code == 200
    for response in (primary, secondary):
        assert PRIMARY not in response.text
        assert SECONDARY not in response.text
        assert "primary" not in response.text.casefold()
        assert "secondary" not in response.text.casefold()


def test_secondary_is_optional_and_primary_remains_site_compatible():
    client = TestClient(
        create_app(_settings(api_key_secondary=None)),
        raise_server_exceptions=False,
    )

    response = client.get("/api/v1/sources", headers=_headers(PRIMARY))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Orion-API-Key": "not-a-configured-credential"}],
)
def test_missing_and_incorrect_credentials_return_sanitized_401(headers):
    app = create_app(_settings(rate_limit_read_per_minute=1))
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/v1/sources", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Valid API key required"}
    assert app.state.rate_limiter.bucket_count == 0
    assert PRIMARY not in response.text
    assert SECONDARY not in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_secondary_configuration_is_strong_distinct_and_sanitized():
    short_secondary = "short-secondary-secret"

    with pytest.raises(APIConfigurationError) as short_error:
        get_settings(
            environ={
                "ORION_ENV": "production",
                "ORION_API_KEY": PRIMARY,
                "ORION_API_KEY_SECONDARY": short_secondary,
                "ORION_ALLOWED_ORIGINS": ORIGIN,
            }
        )
    with pytest.raises(APIConfigurationError) as same_error:
        get_settings(
            environ={
                "ORION_ENV": "production",
                "ORION_API_KEY": PRIMARY,
                "ORION_API_KEY_SECONDARY": PRIMARY,
                "ORION_ALLOWED_ORIGINS": ORIGIN,
            }
        )

    assert short_secondary not in str(short_error.value)
    assert PRIMARY not in str(same_error.value)
    assert "32 characters" in str(short_error.value)
    assert "must differ" in str(same_error.value)


def test_read_limit_retry_after_and_window_reset():
    clock = FakeClock()
    client = TestClient(
        create_app(_settings(), rate_limit_clock=clock),
        raise_server_exceptions=False,
    )

    assert client.get("/api/v1/sources", headers=_headers(PRIMARY)).status_code == 200
    assert client.get("/api/v1/sources", headers=_headers(PRIMARY)).status_code == 200
    limited = client.get("/api/v1/sources", headers=_headers(PRIMARY))

    assert limited.status_code == 429
    assert limited.json() == {"detail": "Rate limit exceeded"}
    assert 1 <= int(limited.headers["retry-after"]) <= 60
    assert limited.headers["x-content-type-options"] == "nosniff"
    assert limited.headers["referrer-policy"] == "no-referrer"
    assert limited.headers["x-frame-options"] == "DENY"
    assert limited.headers["cache-control"] == "no-store"
    assert "strict-transport-security" in limited.headers
    assert PRIMARY not in limited.text

    clock.advance(60)
    assert client.get("/api/v1/sources", headers=_headers(PRIMARY)).status_code == 200


def test_read_write_and_search_use_independent_buckets(monkeypatch):
    monkeypatch.setattr(
        research_service,
        "search",
        lambda query, limit: {
            "query": query,
            "origin": "library",
            "results": [],
            "count": 0,
            "metadata": {},
        },
    )
    client = TestClient(
        create_app(
            _settings(
                rate_limit_read_per_minute=1,
                rate_limit_write_per_minute=1,
                rate_limit_search_per_minute=1,
            )
        ),
        raise_server_exceptions=False,
    )

    read = client.get("/api/v1/sources", headers=_headers(PRIMARY))
    write = client.post(
        "/api/v1/library",
        headers=_headers(PRIMARY),
        json={"paper_id": "missing", "favorite": True},
    )
    search = client.post(
        "/api/v1/search",
        headers=_headers(PRIMARY),
        json={"query": "leadership"},
    )

    assert read.status_code == 200
    assert write.status_code == 404
    assert search.status_code == 200
    assert client.get("/api/v1/sources", headers=_headers(PRIMARY)).status_code == 429
    assert client.post(
        "/api/v1/library",
        headers=_headers(PRIMARY),
        json={"paper_id": "missing", "favorite": True},
    ).status_code == 429
    assert client.post(
        "/api/v1/search",
        headers=_headers(PRIMARY),
        json={"query": "leadership"},
    ).status_code == 429


def test_primary_and_secondary_have_independent_quotas():
    client = TestClient(
        create_app(_settings(rate_limit_read_per_minute=1)),
        raise_server_exceptions=False,
    )

    assert client.get("/api/v1/sources", headers=_headers(PRIMARY)).status_code == 200
    assert client.get("/api/v1/sources", headers=_headers(PRIMARY)).status_code == 429
    assert client.get("/api/v1/sources", headers=_headers(SECONDARY)).status_code == 200
    assert client.get("/api/v1/sources", headers=_headers(SECONDARY)).status_code == 429


def test_public_health_and_docs_are_not_limited():
    client = TestClient(
        create_app(_settings(rate_limit_read_per_minute=1)),
        raise_server_exceptions=False,
    )

    for _ in range(5):
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200


def test_arbitrary_invalid_headers_never_create_buckets_or_consume_quota():
    app = create_app(_settings(rate_limit_read_per_minute=1))
    client = TestClient(app, raise_server_exceptions=False)

    for index in range(100):
        response = client.get(
            "/api/v1/sources",
            headers=_headers(f"attacker-controlled-{index}"),
        )
        assert response.status_code == 401

    assert app.state.rate_limiter.bucket_count == 0
    assert client.get("/api/v1/sources", headers=_headers(PRIMARY)).status_code == 200


def test_limiter_memory_is_bounded_to_known_slots_and_categories():
    limiter = InMemoryRateLimiter(
        {category: 2 for category in RateLimitCategory},
        clock=FakeClock(),
    )

    for slot in CredentialSlot:
        for category in RateLimitCategory:
            limiter.consume(slot, category)

    assert limiter.bucket_count == InMemoryRateLimiter.MAX_BUCKETS == 6
    with pytest.raises(ValueError, match="Unknown authenticated"):
        limiter.consume("arbitrary", RateLimitCategory.READ)  # type: ignore[arg-type]
    assert limiter.bucket_count == 6


def test_limiter_removes_inactive_buckets_after_window():
    clock = FakeClock()
    limiter = InMemoryRateLimiter(
        {category: 2 for category in RateLimitCategory},
        clock=clock,
    )
    limiter.consume(CredentialSlot.PRIMARY, RateLimitCategory.READ)

    clock.advance(61)
    limiter.consume(CredentialSlot.SECONDARY, RateLimitCategory.READ)

    assert limiter.bucket_count == 1


def test_limiter_is_thread_safe_under_contention():
    limiter = InMemoryRateLimiter(
        {category: 25 for category in RateLimitCategory},
        clock=FakeClock(),
    )

    def consume_once() -> bool:
        try:
            limiter.consume(CredentialSlot.PRIMARY, RateLimitCategory.READ)
        except RateLimitExceeded:
            return False
        return True

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: consume_once(), range(100)))

    assert sum(results) == 25
    assert limiter.bucket_count == 1


def test_rate_limit_defaults_and_valid_overrides():
    defaults = get_settings(environ={})
    overridden = get_settings(
        environ={
            "ORION_RATE_LIMIT_SEARCH_PER_MINUTE": "7",
            "ORION_RATE_LIMIT_WRITE_PER_MINUTE": "8",
            "ORION_RATE_LIMIT_READ_PER_MINUTE": "9",
        }
    )

    assert defaults.rate_limit_search_per_minute == DEFAULT_RATE_LIMIT_SEARCH_PER_MINUTE
    assert defaults.rate_limit_write_per_minute == DEFAULT_RATE_LIMIT_WRITE_PER_MINUTE
    assert defaults.rate_limit_read_per_minute == DEFAULT_RATE_LIMIT_READ_PER_MINUTE
    assert overridden.rate_limit_search_per_minute == 7
    assert overridden.rate_limit_write_per_minute == 8
    assert overridden.rate_limit_read_per_minute == 9


@pytest.mark.parametrize("invalid", ["0", "-1", "text", str(MAX_RATE_LIMIT_PER_MINUTE + 1)])
@pytest.mark.parametrize(
    "name",
    [
        "ORION_RATE_LIMIT_SEARCH_PER_MINUTE",
        "ORION_RATE_LIMIT_WRITE_PER_MINUTE",
        "ORION_RATE_LIMIT_READ_PER_MINUTE",
    ],
)
def test_invalid_rate_limit_configuration_fails_with_sanitized_error(name, invalid):
    with pytest.raises(APIConfigurationError) as error:
        get_settings(environ={name: invalid})

    assert name in str(error.value)
    if invalid not in {"0", str(MAX_RATE_LIMIT_PER_MINUTE + 1)}:
        assert invalid not in str(error.value)
