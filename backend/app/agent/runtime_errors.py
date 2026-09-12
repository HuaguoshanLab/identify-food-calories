"""Closed, non-sensitive runtime failure metadata shared by graph and service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RuntimeFailureStage = Literal["checkpoint_load", "context_retrieval", "preference_capture", "graph_execution"]


@dataclass(frozen=True, slots=True)
class AgentRuntimeStageError(Exception):
    """Expose only a controlled stage and exception class, never exception text."""

    stage: RuntimeFailureStage
    error_class: str

    @classmethod
    def from_exception(cls, *, stage: RuntimeFailureStage, error: Exception) -> "AgentRuntimeStageError":
        return cls(stage=stage, error_class=type(error).__name__[:80])
