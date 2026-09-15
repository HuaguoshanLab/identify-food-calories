"""Documentation contracts for stable application and business-module roots."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "coverage",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
}
SOURCE_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".json", ".toml", ".yml", ".yaml"}


def _tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def _is_contract_source(path: Path) -> bool:
    return (
        path.suffix in SOURCE_SUFFIXES
        and not any(part in EXCLUDED_PARTS for part in path.parts)
        and not path.parts[0].startswith(".")
    )


APPLICATION_ROOTS = {
    Path("."),
    Path("backend"),
    Path("frontend"),
    Path("admin-frontend"),
}
BUSINESS_CONTAINERS = {
    Path("backend/app"),
    Path("frontend/src/features"),
    Path("admin-frontend/src/features"),
}


def _required_documentation_roots() -> set[Path]:
    """Require docs at stable module boundaries, not every mechanical subdirectory."""

    roots = set(APPLICATION_ROOTS)
    for path in _tracked_paths():
        if not _is_contract_source(path):
            continue
        for container in BUSINESS_CONTAINERS:
            try:
                relative = path.relative_to(container)
            except ValueError:
                continue
            if len(relative.parts) >= 2:
                roots.add(container / relative.parts[0])
    return roots


def test_application_and_business_module_roots_have_boundary_readmes() -> None:
    missing: list[str] = []
    for directory in sorted(_required_documentation_roots()):
        readme = REPOSITORY_ROOT / directory / "README.md"
        if not readme.is_file():
            missing.append(str(directory))

    assert not missing, f"application or business-module roots missing README.md: {missing}"
