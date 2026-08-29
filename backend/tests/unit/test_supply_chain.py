"""Fail-closed validation for the Phase 2 dependency approval gate."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from validate_supply_chain import (
    APPROVED_PACKAGES,
    SCANNER_IDENTITY,
    ValidationError,
    build_manifest_hash,
    validate_evidence,
)

from lock_dependencies import LOCK_HEADER, LockValidationError, _report_packages, check_lock


TIMESTAMP = datetime(2026, 8, 29, 0, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")
HASH = "a" * 64


def _manual_package(name: str, ecosystem: str, version: str) -> dict[str, str]:
    registry = "https://pypi.org/project" if ecosystem == "pypi" else "https://registry.npmjs.org"
    return {
        "name": name,
        "ecosystem": ecosystem,
        "version": version,
        "registry_url": f"{registry}/{name}/{version}",
        "owner": "verified-publisher",
        "repository_url": f"https://github.com/verified/{name}",
        "license": "MIT",
        "published_at": TIMESTAMP,
        "checked_at": TIMESTAMP,
        "reviewer": "security-reviewer",
        "registry_response_sha256": HASH,
    }


def _approved_manual_evidence() -> dict[str, Any]:
    packages = [
        _manual_package(name, ecosystem, version)
        for name, ecosystem, version in APPROVED_PACKAGES
    ]
    manifest: dict[str, Any] = {
        "packages": packages,
        "manifest_sha256": "",
    }
    manifest["manifest_sha256"] = build_manifest_hash(manifest)
    return {
        "schema_version": "supply-chain-evidence/v1",
        "generated_at": TIMESTAMP,
        "status": "approved",
        "manual_manifest": manifest,
    }


def test_pending_evidence_is_schema_valid_but_cannot_be_approved() -> None:
    evidence = {
        "schema_version": "supply-chain-evidence/v1",
        "generated_at": TIMESTAMP,
        "status": "pending",
        "reason": "human approval is required",
    }

    with pytest.raises(ValidationError, match="pending"):
        validate_evidence(evidence)


def test_complete_human_manifest_for_exact_package_set_passes() -> None:
    validate_evidence(_approved_manual_evidence())


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            lambda evidence: evidence["manual_manifest"]["packages"][0].pop("owner"),
            "owner",
        ),
        (
            lambda evidence: evidence["manual_manifest"]["packages"].__setitem__(
                0,
                {
                    **evidence["manual_manifest"]["packages"][0],
                    "version": "0.0.0",
                },
            ),
            "version",
        ),
        (
            lambda evidence: evidence["manual_manifest"].__setitem__(
                "manifest_sha256", "b" * 64
            ),
            "manifest_sha256",
        ),
        (
            lambda evidence: evidence["manual_manifest"]["packages"][0].__setitem__(
                "published_at", "not-a-timestamp"
            ),
            "published_at",
        ),
    ],
)
def test_human_manifest_tampering_or_missing_fields_fails(
    mutate: object, reason: str
) -> None:
    evidence = copy.deepcopy(_approved_manual_evidence())
    mutate(evidence)  # type: ignore[operator]
    if reason != "manifest_sha256":
        evidence["manual_manifest"]["manifest_sha256"] = build_manifest_hash(
            evidence["manual_manifest"]
        )

    with pytest.raises(ValidationError, match=reason):
        validate_evidence(evidence)


def test_unknown_or_unpinned_scanner_is_rejected_even_when_present() -> None:
    package_results = [
        {
            "name": name,
            "ecosystem": ecosystem,
            "version": version,
            "status": "approved",
            "artifact_sha256": HASH,
        }
        for name, ecosystem, version in APPROVED_PACKAGES
    ]
    evidence = {
        "schema_version": "supply-chain-evidence/v1",
        "generated_at": TIMESTAMP,
        "status": "approved",
        "scanner": {
            **SCANNER_IDENTITY,
            "scanner_name": "slopcheck-on-path",
            "invocation": ["slopcheck", "scan"],
            "package_results": package_results,
        },
    }

    with pytest.raises(ValidationError, match="scanner_name"):
        validate_evidence(evidence)


def test_evidence_must_use_exactly_one_approval_branch() -> None:
    evidence = _approved_manual_evidence()
    evidence["scanner"] = dict(SCANNER_IDENTITY)

    with pytest.raises(ValidationError, match="exactly one"):
        validate_evidence(evidence)


def test_lock_check_accepts_exact_direct_dependencies_and_hashes(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    lock = tmp_path / "requirements.lock"
    pyproject.write_text(
        "[project]\nname = \"demo\"\ndependencies = [\"alpha==1.0.0\"]\n\n"
        "[project.optional-dependencies]\ndev = [\"beta==2.0.0\"]\n",
        encoding="utf-8",
    )
    lock.write_text(
        f"{LOCK_HEADER}\n"
        "# direct-dependency: alpha==1.0.0\n"
        "# direct-dependency: beta==2.0.0\n"
        "alpha==1.0.0 --hash=sha256:" + HASH + "\n"
        "beta==2.0.0 --hash=sha256:" + HASH + "\n"
        "transitive==3.0.0 --hash=sha256:" + HASH + "\n",
        encoding="utf-8",
    )

    check_lock(pyproject, lock)


@pytest.mark.parametrize(
    ("replacement", "reason"),
    [
        ("# direct-dependency: beta==2.1.0", "pyproject drift"),
        ("alpha==1.0.0", "SHA-256"),
    ],
)
def test_lock_check_rejects_direct_dependency_drift_or_missing_hash(
    tmp_path: Path, replacement: str, reason: str
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    lock = tmp_path / "requirements.lock"
    pyproject.write_text(
        "[project]\nname = \"demo\"\ndependencies = [\"alpha==1.0.0\"]\n\n"
        "[project.optional-dependencies]\ndev = [\"beta==2.0.0\"]\n",
        encoding="utf-8",
    )
    lock.write_text(
        f"{LOCK_HEADER}\n"
        "# direct-dependency: alpha==1.0.0\n"
        f"{replacement}\n"
        "alpha==1.0.0 --hash=sha256:" + HASH + "\n"
        "beta==2.0.0 --hash=sha256:" + HASH + "\n",
        encoding="utf-8",
    )

    with pytest.raises(LockValidationError, match=reason):
        check_lock(pyproject, lock)


def test_lock_report_excludes_the_local_project_but_requires_remote_hashes() -> None:
    packages = _report_packages(
        {
            "install": [
                {
                    "metadata": {"name": "food-agent-backend", "version": "0.1.0"},
                    "download_info": {"url": "file:///workspace/backend", "dir_info": {}},
                },
                {
                    "metadata": {"name": "remote-package", "version": "1.0.0"},
                    "download_info": {
                        "url": "https://files.example/remote-package.whl",
                        "archive_info": {"hash": "sha256=" + HASH},
                    },
                },
            ]
        }
    )

    assert packages == {"remote-package": ("remote-package", "1.0.0", HASH)}
