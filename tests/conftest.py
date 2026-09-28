from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class FakeResponse:
    payload: object = None
    text: str = ""
    error: Exception | None = None

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Keep every test away from production data, reports, secrets, and APIs."""
    data_path = tmp_path / "data-store.db"
    platform_path = tmp_path / "platform-store.db"
    monkeypatch.setenv("PIO_DB_PATH", str(data_path))
    monkeypatch.setenv("ORION_DB_PATH", str(platform_path))
    for name in (
        "OPENAI_API_KEY",
        "OPENALEX_API_KEY",
        "SEMANTIC_SCHOLAR_API_KEY",
        "COURTLISTENER_API_TOKEN",
        "DATABASE_URL",
        "ORION_API_KEY",
        "ORION_API_KEY_SECONDARY",
        "ORION_ALLOWED_ORIGINS",
        "ORION_ENV",
        "ORION_RATE_LIMIT_SEARCH_PER_MINUTE",
        "ORION_RATE_LIMIT_WRITE_PER_MINUTE",
        "ORION_RATE_LIMIT_READ_PER_MINUTE",
    ):
        monkeypatch.delenv(name, raising=False)

    import data_store

    monkeypatch.setattr(data_store, "DB_PATH", data_path)


@pytest.fixture
def sample_paper():
    return {
        "id": "doi:10.1234/orion",
        "title": "Liderazgo y seguridad psicológica",
        "authors": "Ana Pérez, John Doe",
        "year": 2025,
        "published_date": "2025-04-03",
        "source": "OpenAlex",
        "journal": "Revista PIO",
        "work_type": "article",
        "doi": "10.1234/orion",
        "url": "https://doi.org/10.1234/orion",
        "abstract": "Evidencia sobre liderazgo, equipos y seguridad psicológica.",
        "topics": "leadership, psychological safety",
        "discovered_via": "OpenAlex",
        "cited_by_count": 7,
        "relevance_score": 12.5,
    }


@pytest.fixture
def fake_response():
    return FakeResponse
