"""Validate pinned supply-chain evidence without executing a scanner from PATH.

This gate intentionally accepts evidence only.  It never downloads packages or
executes ``slopcheck``: a visible executable is not proof of its provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCHEMA_VERSION = "supply-chain-evidence/v1"
APPROVED_PACKAGES: tuple[tuple[str, str, str], ...] = (
    ("langgraph", "pypi", "1.2.11"),
    ("langgraph-checkpoint-postgres", "pypi", "3.1.2"),
    ("eventsource-parser", "npm", "3.1.0"),
    ("arize-phoenix", "pypi", "20.3.0"),
    ("arize-phoenix-otel", "pypi", "0.17.1"),
    ("openinference-instrumentation-langchain", "pypi", "0.1.72"),
    ("promptfoo", "npm", "0.122.0"),
)
SCANNER_IDENTITY: dict[str, str] = {
    "scanner_name": "slopcheck",
    "scanner_version": "0.6.1",
    "source_repository": "https://github.com/0xToxSec/slopcheck",
    "release_artifact_sha256": "5d00bd5a235b46d5775f3a7d868bbca2eacf6b33211894ffaaaa6d8f3ea3dac8",
}

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
EXPECTED_PACKAGE_SET = set(APPROVED_PACKAGES)
PACKAGE_FIELDS = {
    "name",
    "ecosystem",
    "version",
    "registry_url",
    "owner",
    "repository_url",
    "license",
    "published_at",
    "checked_at",
    "reviewer",
    "registry_response_sha256",
}


class ValidationError(ValueError):
    """The evidence cannot authorize an install."""


def _as_object(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be an object")
    return value


def _as_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{path} must be a non-empty string")
    return value


def _validate_timestamp(value: object, path: str) -> None:
    text = _as_string(value, path)
    if not text.endswith("Z"):
        raise ValidationError(f"{path} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError(f"{path} must be an ISO-8601 timestamp") from error


def _validate_sha256(value: object, path: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValidationError(f"{path} must be a lowercase SHA-256 hex digest")


def _validate_https_url(value: object, path: str) -> str:
    url = _as_string(value, path)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValidationError(f"{path} must be an HTTPS URL")
    return url


def build_manifest_hash(manifest: dict[str, object]) -> str:
    """Hash a manifest's signed content, excluding its self-referential hash."""

    signed = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    payload = json.dumps(
        signed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_package(record: object, index: int) -> tuple[str, str, str]:
    package = _as_object(record, f"packages[{index}]")
    actual_fields = set(package)
    if actual_fields != PACKAGE_FIELDS:
        missing = sorted(PACKAGE_FIELDS - actual_fields)
        extras = sorted(actual_fields - PACKAGE_FIELDS)
        raise ValidationError(
            f"packages[{index}] fields mismatch; missing={missing}, extra={extras}"
        )

    name = _as_string(package["name"], f"packages[{index}].name")
    ecosystem = _as_string(package["ecosystem"], f"packages[{index}].ecosystem")
    version = _as_string(package["version"], f"packages[{index}].version")
    if ecosystem not in {"pypi", "npm"}:
        raise ValidationError(f"packages[{index}].ecosystem must be pypi or npm")
    expected_registry_host = "pypi.org" if ecosystem == "pypi" else "www.npmjs.com"
    registry_url = _validate_https_url(
        package["registry_url"], f"packages[{index}].registry_url"
    )
    if urlparse(registry_url).netloc != expected_registry_host:
        raise ValidationError(
            f"packages[{index}].registry_url must use {expected_registry_host}"
        )
    if name not in registry_url or version not in registry_url:
        raise ValidationError(
            f"packages[{index}].registry_url must identify the exact name and version"
        )
    _as_string(package["owner"], f"packages[{index}].owner")
    _validate_https_url(package["repository_url"], f"packages[{index}].repository_url")
    _as_string(package["license"], f"packages[{index}].license")
    _validate_timestamp(package["published_at"], f"packages[{index}].published_at")
    _validate_timestamp(package["checked_at"], f"packages[{index}].checked_at")
    _as_string(package["reviewer"], f"packages[{index}].reviewer")
    _validate_sha256(
        package["registry_response_sha256"],
        f"packages[{index}].registry_response_sha256",
    )
    return name, ecosystem, version


def _validate_exact_package_set(records: object, path: str) -> None:
    if not isinstance(records, list):
        raise ValidationError(f"{path} must be a list")
    actual = {_validate_package(record, index) for index, record in enumerate(records)}
    if len(actual) != len(records):
        raise ValidationError(f"{path} contains duplicate package records")
    if actual != EXPECTED_PACKAGE_SET:
        raise ValidationError(
            f"{path} package set mismatch; expected={sorted(EXPECTED_PACKAGE_SET)}, actual={sorted(actual)}"
        )


def _validate_manual_manifest(value: object) -> None:
    manifest = _as_object(value, "manual_manifest")
    if set(manifest) != {"packages", "manifest_sha256"}:
        raise ValidationError("manual_manifest must contain only packages and manifest_sha256")
    _validate_sha256(manifest["manifest_sha256"], "manual_manifest.manifest_sha256")
    expected_hash = build_manifest_hash(manifest)
    if manifest["manifest_sha256"] != expected_hash:
        raise ValidationError("manual_manifest.manifest_sha256 does not match canonical content")
    _validate_exact_package_set(manifest["packages"], "manual_manifest.packages")


def _validate_scanner(value: object) -> None:
    scanner = _as_object(value, "scanner")
    required = {*SCANNER_IDENTITY, "invocation", "package_results"}
    if set(scanner) != required:
        raise ValidationError(f"scanner fields must be exactly {sorted(required)}")
    for field, expected in SCANNER_IDENTITY.items():
        if scanner[field] != expected:
            raise ValidationError(f"scanner.{field} must match the pinned scanner identity")
    invocation = scanner["invocation"]
    if not isinstance(invocation, list) or len(invocation) < 2:
        raise ValidationError("scanner.invocation must record a non-empty structured command")
    if any(not isinstance(argument, str) or not argument for argument in invocation):
        raise ValidationError("scanner.invocation arguments must be non-empty strings")
    _validate_exact_package_set(scanner["package_results"], "scanner.package_results")


def validate_evidence(evidence: object) -> None:
    """Raise ValidationError unless evidence authorizes only the seven exact packages."""

    document = _as_object(evidence, "evidence")
    for field in ("schema_version", "generated_at", "status"):
        if field not in document:
            raise ValidationError(f"evidence.{field} is required")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ValidationError(f"evidence.schema_version must be {SCHEMA_VERSION}")
    _validate_timestamp(document["generated_at"], "evidence.generated_at")
    status = document["status"]
    if status == "pending":
        _as_string(document.get("reason"), "evidence.reason")
        if "scanner" in document or "manual_manifest" in document:
            raise ValidationError("pending evidence must not carry an approval branch")
        raise ValidationError("evidence is pending human review and cannot authorize install")
    if status != "approved":
        raise ValidationError("evidence.status must be pending or approved")
    approval_branches = [key for key in ("scanner", "manual_manifest") if key in document]
    if len(approval_branches) != 1:
        raise ValidationError("approved evidence must use exactly one approval branch")
    unexpected = set(document) - {"schema_version", "generated_at", "status", *approval_branches}
    if unexpected:
        raise ValidationError(f"evidence has unexpected fields: {sorted(unexpected)}")
    if approval_branches[0] == "scanner":
        _validate_scanner(document["scanner"])
    else:
        _validate_manual_manifest(document["manual_manifest"])


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValidationError(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValidationError(f"invalid JSON in {path}: {error}") from error


def _self_test() -> None:
    package_records = [
        {
            "name": name,
            "ecosystem": ecosystem,
            "version": version,
            "registry_url": (
                f"https://pypi.org/project/{name}/{version}"
                if ecosystem == "pypi"
                else f"https://www.npmjs.com/package/{name}/v/{version}"
            ),
            "owner": "security-reviewer",
            "repository_url": f"https://github.com/example/{name}",
            "license": "MIT",
            "published_at": "2026-08-29T00:00:00Z",
            "checked_at": "2026-08-29T00:00:00Z",
            "reviewer": "security-reviewer",
            "registry_response_sha256": "a" * 64,
        }
        for name, ecosystem, version in APPROVED_PACKAGES
    ]
    manifest: dict[str, object] = {"packages": package_records, "manifest_sha256": ""}
    manifest["manifest_sha256"] = build_manifest_hash(manifest)
    validate_evidence(
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": "2026-08-29T00:00:00Z",
            "status": "approved",
            "manual_manifest": manifest,
        }
    )
    try:
        validate_evidence(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": "2026-08-29T00:00:00Z",
                "status": "pending",
                "reason": "human review required",
            }
        )
    except ValidationError:
        return
    raise AssertionError("pending evidence must fail closed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify", help="validate a pinned evidence file")
    verify.add_argument("--schema", type=Path, required=True)
    verify.add_argument("--evidence", type=Path, required=True)
    subparsers.add_parser("self-test", help="run deterministic validator smoke checks")
    args = parser.parse_args(argv)
    try:
        if args.command == "self-test":
            _self_test()
        else:
            schema = _as_object(_load_json(args.schema), "schema")
            if schema.get("$id") != "https://food-agent.local/schemas/supply-chain-evidence/v1":
                raise ValidationError("schema is not the pinned supply-chain evidence v1 contract")
            validate_evidence(_load_json(args.evidence))
    except (AssertionError, ValidationError) as error:
        print(f"SUPPLY-CHAIN GATE: FAIL: {error}", file=sys.stderr)
        return 1
    print("SUPPLY-CHAIN GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
