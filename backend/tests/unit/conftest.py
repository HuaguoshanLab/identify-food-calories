"""Explicit historical evidence baselines for offline contract tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def historical_phase063_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise report semantics against its recorded sources, never certify HEAD.

    Fresh PostgreSQL integration evaluations prove current-source compatibility.
    This opt-in fixture leaves report bytes and the production validator intact.
    """
    from evals.phase_06_3 import evaluate

    path = Path(__file__).parents[2] / "evals/phase_06_3/release.json"
    hashes = json.loads(path.read_text(encoding="utf-8"))["input_hashes"]
    monkeypatch.setattr(evaluate, "_release_input_hashes", lambda: dict(hashes))
