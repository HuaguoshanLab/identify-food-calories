"""Repository documentation contracts for tracked source directories."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_SECTIONS = ("## 职责", "## 允许依赖", "## 文件索引")
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


def _documented_directories() -> set[Path]:
    directories = {Path(".")}
    for path in _tracked_paths():
        if not _is_contract_source(path):
            continue
        current = path.parent
        while current != Path("."):
            directories.add(current)
            current = current.parent
    return directories


def test_every_tracked_source_directory_has_a_three_section_readme() -> None:
    missing: list[str] = []
    incomplete: list[str] = []
    for directory in sorted(_documented_directories()):
        readme = REPOSITORY_ROOT / directory / "README.md"
        if not readme.is_file():
            missing.append(str(directory))
            continue
        content = readme.read_text(encoding="utf-8")
        absent = [section for section in REQUIRED_SECTIONS if section not in content]
        if absent:
            incomplete.append(f"{directory}: {', '.join(absent)}")

    assert not missing, f"source directories missing README.md: {missing}"
    assert not incomplete, f"README sections missing: {incomplete}"


def test_parent_readme_indexes_each_direct_child_source_directory() -> None:
    directories = _documented_directories()
    omissions: list[str] = []
    for child in sorted(directory for directory in directories if directory != Path(".")):
        parent = child.parent
        parent_readme = (REPOSITORY_ROOT / parent / "README.md").read_text(encoding="utf-8")
        child_name = child.name
        if f"`{child_name}/`" not in parent_readme and f"`{child_name}`" not in parent_readme:
            omissions.append(f"{parent}/README.md does not index {child}/")

    assert not omissions, "parent directory indexes are stale: " + "; ".join(omissions)
