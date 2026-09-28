from __future__ import annotations

import re
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

WORKFLOW_DIRECTORY = Path(".github/workflows")
USE_PATTERN = re.compile(
    r"^\s*-?\s*uses:\s*([^\s@]+)@([^\s#]+)(?:\s+#\s*(\S+))?\s*$",
    re.MULTILINE,
)
FULL_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
EXPECTED_SCHEDULES = {
    "daily-radar.yml": 'cron: "0 11 * * *"',
    "weekly-radar.yml": 'cron: "0 12 * * 5"',
    "orion-health-monitor.yml": 'cron: "17 * * * *"',
}


def _workflows() -> list[Path]:
    workflows = sorted(WORKFLOW_DIRECTORY.glob("*.yml"))
    assert workflows
    return workflows


def test_all_external_actions_are_pinned_to_documented_full_shas():
    found_action = False

    for workflow in _workflows():
        contents = workflow.read_text(encoding="utf-8")
        for repository, revision, documented_tag in USE_PATTERN.findall(contents):
            if repository.startswith("./"):
                continue
            found_action = True
            assert FULL_SHA_PATTERN.fullmatch(revision), (
                f"{workflow}: {repository} must use a full commit SHA"
            )
            assert documented_tag and re.fullmatch(r"v\d+(?:\.\d+)*", documented_tag), (
                f"{workflow}: {repository} must retain its release tag as a comment"
            )

    assert found_action


def test_every_checkout_disables_persisted_credentials():
    for workflow in _workflows():
        contents = workflow.read_text(encoding="utf-8")
        checkout_count = sum(
            repository == "actions/checkout"
            for repository, _, _ in USE_PATTERN.findall(contents)
        )
        assert contents.count("persist-credentials: false") == checkout_count


def test_normal_workflows_have_read_only_permissions_and_no_pushes():
    for workflow in _workflows():
        contents = workflow.read_text(encoding="utf-8")
        assert "contents: read" in contents
        assert "contents: write" not in contents
        assert "packages: write" not in contents
        assert "pull-requests: write" not in contents
        assert "git push" not in contents
        assert not re.search(r"\becho\b[^\n]*\$\{\{\s*secrets\.", contents)
        assert not re.search(r"\brun:\s*[^\n]*\$\{\{\s*github\.event", contents)

        if workflow.name != "codeql.yml":
            assert "security-events: write" not in contents


def test_codeql_has_only_required_elevated_permission_and_python_language():
    contents = (WORKFLOW_DIRECTORY / "codeql.yml").read_text(encoding="utf-8")

    assert contents.count("security-events: write") == 1
    assert "contents: read" in contents
    assert re.search(r"languages:\s*python\b", contents)
    assert "pull_request:" in contents
    assert re.search(r"push:\s*\n\s+branches:\s*\n\s+- main", contents)
    assert "schedule:" in contents
    assert "actions: write" not in contents
    assert "checks: write" not in contents


def test_dependency_audit_is_secret_free_read_only_and_unsuppressed():
    contents = (WORKFLOW_DIRECTORY / "dependency-audit.yml").read_text(
        encoding="utf-8"
    )

    assert 'python-version: "3.12"' in contents
    assert "contents: read" in contents
    assert "pull_request:" in contents
    assert "workflow_dispatch:" in contents
    assert "schedule:" in contents
    assert "requirements.txt" in contents
    assert "pip_audit" in contents
    assert "secrets." not in contents
    assert "DATABASE_URL" not in contents
    assert "ORION_API_KEY" not in contents
    assert "--ignore-vuln" not in contents
    assert "continue-on-error" not in contents


def test_operational_schedules_remain_unchanged():
    for filename, expected_schedule in EXPECTED_SCHEDULES.items():
        contents = (WORKFLOW_DIRECTORY / filename).read_text(encoding="utf-8")
        assert expected_schedule in contents
