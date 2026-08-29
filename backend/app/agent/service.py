"""Application transaction boundary for Agent threads, runs, events and invocations."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.agent.models import AgentEvent, AgentInvocation, AgentLease, AgentRun, AgentThread
from app.agent.ports import AgentRepository
from app.agent.state import AgentNextAction, AgentRuntimeStatus, MealAgentState
from app.agent.graph import AgentGraph
from langgraph.types import Command


class AgentThreadUnavailable(LookupError):
    """Uniform missing/foreign-thread result; callers must not leak ownership details."""


class AgentCommandConflict(ValueError):
    """A client idempotency key was reused for a different canonical command."""


class AgentLeaseUnavailable(RuntimeError):
    """Another worker currently owns the persisted execution lease."""


GRAPH_VERSION = "meal-agent-graph.v1"
PROMPT_VERSION = "reasoning-parse.v1"
TOOL_VERSION = "nutrition-tools-v1"


def canonical_command_hash(command: dict[str, object]) -> str:
    """Hash canonical JSON; only the digest reaches durable idempotency metadata."""

    payload = json.dumps(command, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AgentService:
    """Coordinates durable Agent state while keeping graph and ORM concerns separate."""

    def __init__(
        self,
        *,
        repository: AgentRepository,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def create_thread(self, *, user_id: uuid.UUID) -> AgentThread:
        now = self._now()
        thread = self._repository.add_thread(
            AgentThread(
                id=uuid.uuid4(),
                user_id=user_id,
                status="open",
                revision=0,
                created_at=now,
                last_activity_at=now,
                deleted_at=None,
            )
        )
        self._commit_or_rollback()
        return thread

    def get_thread(self, *, thread_id: uuid.UUID, user_id: uuid.UUID) -> AgentThread:
        thread = self._repository.get_thread_for_user(thread_id=thread_id, user_id=user_id)
        if thread is None or thread.deleted_at is not None:
            raise AgentThreadUnavailable("agent thread is unavailable")
        return thread

    def create_or_reuse_run(
        self,
        *,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        command_key: str,
        canonical_command: dict[str, object],
    ) -> AgentRun:
        thread = self._repository.get_thread_for_user(
            thread_id=thread_id, user_id=user_id, for_update=True
        )
        if thread is None or thread.deleted_at is not None:
            raise AgentThreadUnavailable("agent thread is unavailable")
        command_hash = canonical_command_hash(canonical_command)
        existing = self._repository.get_run_for_command_for_user(
            thread_id=thread_id,
            user_id=user_id,
            command_key=command_key,
            for_update=True,
        )
        if existing is not None:
            if existing.command_hash != command_hash:
                raise AgentCommandConflict("idempotency key payload mismatch")
            return existing
        now = self._now()
        run = self._repository.add_run(
            AgentRun(
                id=uuid.uuid4(),
                thread_id=thread_id,
                user_id=user_id,
                command_key=command_key,
                command_hash=command_hash,
                status="accepted",
                graph_version=GRAPH_VERSION,
                prompt_version=PROMPT_VERSION,
                tool_version=TOOL_VERSION,
                model_provider=None,
                model_version=None,
                graph_steps=0,
                model_calls=0,
                tool_calls=0,
                elapsed_ms=0,
                estimated_cost_usd=Decimal("0"),
                failure_code=None,
                created_at=now,
                updated_at=now,
                finished_at=None,
            )
        )
        thread.last_activity_at = now
        thread.revision += 1
        self._commit_or_rollback()
        return run

    async def execute_run(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        graph: AgentGraph,
        checkpointer: object,
        input_text: str | None = None,
        resume_payload: dict[str, object] | None = None,
    ) -> AgentRun:
        """Execute one accepted run after tenant ownership has been checked by the caller.

        The command body is transient: durable records receive only event type, progress and the
        deterministic report.  Provider request text and state messages never enter the ledger.
        """

        run = self._repository.get_run_for_user(run_id=run_id, user_id=user_id, for_update=True)
        if run is None:
            raise AgentThreadUnavailable("agent run is unavailable")
        if run.status == "completed" and resume_payload is None:
            return run
        self.get_thread(thread_id=run.thread_id, user_id=user_id)
        run.status = "running"
        run.updated_at = self._now()
        self._commit_or_rollback()
        self.append_safe_event(
            thread_id=run.thread_id,
            user_id=user_id,
            run_id=run.id,
            event_type="running",
            payload={"run_id": str(run.id)},
            safe_summary="分析任务正在运行。",
        )
        previous = await self._load_checkpoint(checkpointer=checkpointer, thread_id=run.thread_id)
        if resume_payload is not None and previous is not None:
            # Command is intentionally constructed at the API/service recovery boundary.  The
            # graph consumes only its validated JSON body and therefore never needs HTTP or ORM.
            command: Command = Command(resume=resume_payload)
            state = previous.model_copy(
                update={
                    "run_id": run.id,
                    "status": AgentRuntimeStatus.ACCEPTED,
                }
            )
            finished = await graph.ainvoke(state, resume=command.resume)
        elif input_text is not None:
            state = MealAgentState(
                user_id=user_id,
                thread_id=run.thread_id,
                run_id=run.id,
                messages=(input_text,),
                graph_version=run.graph_version,
                prompt_version=run.prompt_version,
                tool_version=run.tool_version,
                next_action=AgentNextAction.PARSE,
                status=AgentRuntimeStatus.ACCEPTED,
            )
            finished = await graph.ainvoke(state)
        else:
            run.status = "failed"
            run.failure_code = "MISSING_AGENT_COMMAND"
            run.finished_at = self._now()
            self._commit_or_rollback()
            return run
        await self._persist_checkpoint(checkpointer=checkpointer, state=finished)
        run = self._repository.get_run_for_user(run_id=run.id, user_id=user_id, for_update=True)
        assert run is not None
        run.graph_steps = max(run.graph_steps, 1)
        run.model_calls = max(run.model_calls, 1)
        run.tool_calls = len(finished.tool_summaries)
        run.updated_at = self._now()
        if finished.status is AgentRuntimeStatus.WAITING_INPUT:
            run.status = "waiting_input"
            run.finished_at = None
            self._commit_or_rollback()
            self.append_safe_event(
                thread_id=run.thread_id,
                user_id=user_id,
                run_id=run.id,
                event_type="waiting_input",
                payload={"run_id": str(run.id), "report": finished.report or {}},
                safe_summary="需要补充信息后才能继续分析。",
            )
            return run
        if finished.status is AgentRuntimeStatus.COMPLETED and finished.report is not None:
            run.status = "completed"
            run.finished_at = run.updated_at
            self._commit_or_rollback()
            self.append_safe_event(
                thread_id=run.thread_id,
                user_id=user_id,
                run_id=run.id,
                event_type="completed",
                payload={"run_id": str(run.id), "report": finished.report},
                safe_summary="分析报告已生成。",
            )
            return run
        run.status = "failed"
        run.failure_code = "ANALYSIS_NOT_COMPLETED"
        run.finished_at = run.updated_at
        self._commit_or_rollback()
        self.append_safe_event(
            thread_id=run.thread_id,
            user_id=user_id,
            run_id=run.id,
            event_type="failed",
            payload={"run_id": str(run.id)},
            safe_summary="分析未能完成。",
        )
        return run

    async def resume_payload_for_text(
        self, *, checkpointer: object, thread_id: uuid.UUID, text: str
    ) -> dict[str, object] | None:
        """Turn the existing public text command into a narrow validated resume payload.

        The frozen API contract deliberately has no raw graph-state field.  The UI can submit a
        JSON object for multi-question controls, while a one-question text answer remains usable.
        Invalid text returns ``None`` and leaves the checkpoint waiting.
        """

        state = await self._load_checkpoint(checkpointer=checkpointer, thread_id=thread_id)
        if state is None:
            return None
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            candidate = None
        if isinstance(candidate, dict) and set(candidate) <= {"answers", "corrections"}:
            return candidate
        if state.next_action is AgentNextAction.ASK_USER and len(state.clarification_questions) == 1:
            question = state.clarification_questions[0]
            if question.field == "grams":
                matched = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:g|克)?", text, re.IGNORECASE)
                if matched is not None:
                    return {"answers": {question.item_id: {"grams": matched.group(1)}}}
            if question.field == "food":
                normalized = " ".join(text.casefold().split())
                for index, food in enumerate(question.candidates, start=1):
                    if normalized in {str(index), " ".join(food.label.casefold().split())}:
                        return {"answers": {question.item_id: {"candidate_id": str(food.food_id)}}}
        return None

    @staticmethod
    async def _load_checkpoint(
        *, checkpointer: object, thread_id: uuid.UUID
    ) -> MealAgentState | None:
        saver = checkpointer
        checkpoint_tuple = await saver.aget_tuple(  # type: ignore[attr-defined]
            {"configurable": {"thread_id": str(thread_id), "checkpoint_ns": "meal-analysis"}}
        )
        if checkpoint_tuple is None:
            return None
        values = checkpoint_tuple.checkpoint.get("channel_values", {})
        raw_state = values.get("agent_state")
        return MealAgentState.model_validate(raw_state) if isinstance(raw_state, dict) else None

    @staticmethod
    async def _persist_checkpoint(*, checkpointer: object, state: MealAgentState) -> None:
        """Persist short-lived graph state after terminal routing without exposing it as a snapshot."""

        from langgraph.checkpoint.base import empty_checkpoint

        saver = checkpointer
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {"agent_state": state.model_dump(mode="json")}
        checkpoint["channel_versions"] = {"agent_state": "0000000000000001.0"}
        await saver.aput(  # type: ignore[attr-defined]
            {
                "configurable": {
                    "thread_id": str(state.thread_id),
                    "checkpoint_ns": "meal-analysis",
                }
            },
            checkpoint,
            {"source": "loop", "step": 1, "parents": {}},
            {"agent_state": "0000000000000001.0"},
        )

    def append_safe_event(
        self,
        *,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
        event_type: str,
        payload: dict[str, object],
        safe_summary: str,
    ) -> AgentEvent:
        self.get_thread(thread_id=thread_id, user_id=user_id)
        if run_id is not None and self._repository.get_run_for_user(run_id=run_id, user_id=user_id) is None:
            raise AgentThreadUnavailable("agent run is unavailable")
        event = self._repository.add_event(
            AgentEvent(
                id=uuid.uuid4(),
                thread_id=thread_id,
                run_id=run_id,
                user_id=user_id,
                seq=self._repository.next_event_seq_for_thread_for_user(
                    thread_id=thread_id, user_id=user_id
                ),
                event_type=event_type,
                payload=payload,
                safe_summary=safe_summary,
                created_at=self._now(),
            )
        )
        self._commit_or_rollback()
        return event

    def latest_run_and_events(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, after_seq: int = 0
    ) -> tuple[AgentThread, AgentRun | None, list[AgentEvent]]:
        """Return only tenant-filtered business ledger data for snapshot/SSE presenters."""

        thread = self.get_thread(thread_id=thread_id, user_id=user_id)
        return (
            thread,
            self._repository.get_latest_run_for_thread_for_user(
                thread_id=thread_id, user_id=user_id
            ),
            self._repository.list_events_for_thread_for_user(
                thread_id=thread_id, user_id=user_id, after_seq=after_seq
            ),
        )

    def prepare_invocation(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        node_name: str,
        item_key: str,
        input_version: str,
        operation_version: str,
        request_hash: str,
    ) -> AgentInvocation:
        run = self._repository.get_run_for_user(run_id=run_id, user_id=user_id, for_update=True)
        if run is None:
            raise AgentThreadUnavailable("agent run is unavailable")
        existing = self._repository.get_invocation_for_user_for_update(
            run_id=run_id,
            user_id=user_id,
            node_name=node_name,
            item_key=item_key,
            input_version=input_version,
            operation_version=operation_version,
            request_hash=request_hash,
        )
        if existing is not None:
            return existing
        now = self._now()
        invocation = self._repository.add_invocation(
            AgentInvocation(
                id=uuid.uuid4(),
                thread_id=run.thread_id,
                run_id=run.id,
                user_id=user_id,
                node_name=node_name,
                item_key=item_key,
                input_version=input_version,
                operation_version=operation_version,
                request_hash=request_hash,
                status="prepared",
                attempt=0,
                cost_usd=Decimal("0"),
                safe_result_digest=None,
                failure_code=None,
                created_at=now,
                updated_at=now,
            )
        )
        self._commit_or_rollback()
        return invocation

    def claim_lease(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        holder_id: str,
        duration: timedelta,
    ) -> AgentLease:
        if duration <= timedelta(0):
            raise ValueError("lease duration must be positive")
        if self._repository.get_run_for_user(run_id=run_id, user_id=user_id, for_update=True) is None:
            raise AgentThreadUnavailable("agent run is unavailable")
        now = self._now()
        lease = self._repository.get_lease_for_run_for_update(run_id=run_id, user_id=user_id)
        if lease is not None and lease.expires_at > now and lease.holder_id != holder_id:
            raise AgentLeaseUnavailable("agent run is leased")
        if lease is None:
            lease = self._repository.add_lease(
                AgentLease(
                    id=uuid.uuid4(),
                    run_id=run_id,
                    holder_id=holder_id,
                    acquired_at=now,
                    expires_at=now + duration,
                )
            )
        else:
            lease.holder_id = holder_id
            lease.acquired_at = now
            lease.expires_at = now + duration
        self._commit_or_rollback()
        return lease

    def _commit_or_rollback(self) -> None:
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
