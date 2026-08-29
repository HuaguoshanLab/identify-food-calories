"""Fail-closed validation for the Phase 2 dependency approval gate."""

from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from validate_supply_chain import (
    APPROVED_PACKAGES,
    SCANNER_IDENTITY,
    ValidationError,
    build_manifest_hash,
    validate_evidence,
)


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


def _approved_manual_evidence() -> dict[str, object]:
    packages = [
        _manual_package(name, ecosystem, version)
        for name, ecosystem, version in APPROVED_PACKAGES
    ]
    manifest = {
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
