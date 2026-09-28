# Testing Orion

## Setup

Use Python 3.12 and install development dependencies separately from the production requirements:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Run the suite

The standard local and CI suite excludes optional network diagnostics:

```bash
PYTHONPATH=. python -m pytest -m "not network and not postgres" -q
```

Run coverage for the central modules with the same 90% regression floor used by CI:

```bash
PYTHONPATH=. python -m pytest -m "not network and not postgres" -q \
  --cov=database --cov=research_agent --cov=data_store --cov=platform_store \
  --cov=orion_platform --cov=export_utils \
  --cov-report=term-missing --cov-fail-under=90
```

The Phase 2 baseline is 94% total coverage. The principal intentional gaps are optional OpenAI-backed content generators and defensive branches for unavailable optional parsers.

## Markers

- `unit`: isolated, fast logic tests.
- `integration`: SQLite or multi-module tests using temporary resources and mocks.
- `smoke`: basic application startup/import checks.
- `network`: optional manual diagnostics that contact real services; never part of standard CI.
- `postgres`: optional integration tests that require a real PostgreSQL instance; never part of standard CI.

Run a marker directly with `python -m pytest -m unit -q`. Run `network` or `postgres` diagnostics only by explicit choice; these tests may be slow, rate-limited, or require service configuration.

## Adding tests

- Keep tests deterministic: mock HTTP, time, randomness, and external clients.
- Never require OpenAI, Semantic Scholar, CourtListener, or other secrets in CI.
- Use `tmp_path` for every test database and report directory. Never read from or write to `pio_dashboard.db`.
- Reuse fixtures in `tests/conftest.py`; use synthetic, non-sensitive data.
- Reproduce a bug with a failing test before changing functional code.
- Do not use real sleeps or depend on test order, local paths, shared state, or internet access.
