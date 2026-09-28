# Orion Repository Guidance

## Branches and pull requests

- Do not work directly on `main`; create a focused feature or fix branch.
- Keep commits small, clear, and limited to the requested scope.
- Every change must be proposed through a pull request with a summary, validation evidence, security considerations, risks, and rollback notes.
- Do not merge a pull request without the required human review.

## Tests and validation

- Run `python -m compileall -q .` and `PYTHONPATH=. python -m pytest -q` before requesting review.
- Validate edited GitHub Actions YAML files and preserve manual `workflow_dispatch` triggers.
- Fix only failures caused by the current change; report unrelated failures without broad refactors.

## Security and data

- Never commit credentials, API keys, tokens, `.env` files, or Streamlit secrets.
- Use environment variables or GitHub/Streamlit secrets for sensitive configuration.
- Do not expose secrets in logs, fixtures, reports, screenshots, or pull-request text.
- Treat `pio_dashboard.db` and user/research data as protected artifacts: do not overwrite, delete, migrate, or commit incidental changes without explicit approval.
- Avoid destructive commands and preserve existing data and unrelated user changes.

## Infrastructure

- Keep automation reproducible in GitHub Actions and independent of a local computer.
- Preserve existing action versions unless a scoped update is required.
- Do not claim planned cloud services, databases, APIs, monitoring, or controls are already implemented.

## Autonomy levels

- **GREEN:** Read-only inspection, focused documentation, tests, linting, YAML validation, and reversible changes inside an approved branch may proceed autonomously.
- **YELLOW:** Dependency upgrades, workflow behavior changes, schema-compatible data operations, infrastructure configuration, or changes with operational cost require explicit human review before merge or deployment.
- **RED:** Production deployment, secret rotation or access, permission changes, destructive data operations, database migrations, security-boundary changes, and merging to `main` require explicit human approval before execution.
