"""Keep graph orchestration independent of persistence and provider adapters."""

from __future__ import annotations

import ast
from pathlib import Path


GRAPH_SOURCE = Path(__file__).resolve().parents[2] / "app" / "agent" / "graph.py"
FORBIDDEN_MODULE_PARTS = {"api", "models", "repository", "search_repository", "archive_repository"}
FORBIDDEN_ROOTS = {"sqlalchemy", "psycopg"}


def _forbidden_imports(source: str) -> list[str]:
    violations: list[str] = []
    for node in sorted(ast.walk(ast.parse(source)), key=lambda item: getattr(item, "lineno", 0)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
            if not _is_forbidden(node.module):
                names.extend(f"{node.module}.{alias.name}" for alias in node.names)
        else:
            continue

        for name in names:
            if _is_forbidden(name):
                violation = f"line {node.lineno}: {name}"
                if violation not in violations:
                    violations.append(violation)
    return violations


def _is_forbidden(name: str) -> bool:
    parts = name.split(".")
    return (
        parts[0] in FORBIDDEN_ROOTS
        or (parts[0] == "app" and any(part in FORBIDDEN_MODULE_PARTS for part in parts[1:]))
        or (parts[:2] == ["app", "providers"] and len(parts) > 3 and parts[3] not in {"dto", "ports"})
    )


def test_graph_only_imports_orchestration_boundaries() -> None:
    violations = _forbidden_imports(GRAPH_SOURCE.read_text(encoding="utf-8"))
    assert not violations, "Graph must use tools and ports, not persistence or API: " + ", ".join(violations)


def test_boundary_check_catches_nested_and_aliased_imports() -> None:
    source = """\
from app.nutrition.repository import NutritionRepository as Repo
def inner():
    import sqlalchemy as db
from app.nutrition import repository
from app.providers.reasoning import deepseek
"""
    assert _forbidden_imports(source) == [
        "line 1: app.nutrition.repository",
        "line 3: sqlalchemy",
        "line 4: app.nutrition.repository",
        "line 5: app.providers.reasoning.deepseek",
    ]
