"""Application transaction boundary for Agent threads, runs, events and invocations."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.agent.models import (
    AgentDeletionIntent,
    AgentEvent,
    AgentImage,
    AgentInvocation,
    AgentLease,
    AgentRun,
    AgentThread,
    AgentVisionInvocation,
)
from app.images.schemas import ValidatedImageReference
from app.agent.ports import AgentRepository
from app.agent.state import AgentNextAction, AgentRuntimeStatus, MealAgentState, StateImageReference
from app.agent.graph import AgentGraph
from langgraph.types import Command
from langgraph.errors import GraphRecursionError


class AgentThreadUnavailable(LookupError):
    """Uniform missing/foreign-thread result; callers must not leak ownership details."""


class AgentCommandConflict(ValueError):
    """A client idempotency key was reused for a different canonical command."""


class AgentLeaseUnavailable(RuntimeError):
    """Another worker currently owns the persisted execution lease."""


GRAPH_VERSION = "meal-agent-graph.v1"
PROMPT_VERSION = "reasoning-parse.v1"
TOOL_VERSION = "nutrition-tools-v1"
VISION_OPERATION_VERSION = "vision-meal.v1"


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Explicit retention periods supplied by the validated runtime configuration."""

    checkpoint_event_days: int
    audit_days: int
    deletion_due_delta: timedelta
    poll_interval: timedelta


@dataclass(frozen=True, slots=True)
class RetentionSweep:
    """Tenant-bound work selected by Service before the worker touches the saver."""

    due_deletions: tuple[tuple[uuid.UUID, uuid.UUID], ...]
    inactive_threads: tuple[tuple[uuid.UUID, uuid.UUID], ...]
    expired_runs: tuple[tuple[uuid.UUID, uuid.UUID], ...]
    expired_images: tuple[tuple[uuid.UUID, uuid.UUID], ...]
    next_eligible_at: datetime | None


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
        image_reference: StateImageReference | None = None,
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
        try:
            previous = await self._load_checkpoint(checkpointer=checkpointer, thread_id=run.thread_id)
            if resume_payload is None and input_text is None and image_reference is None:
                return await self._fail_run(
                    run=run, user_id=user_id, code="MISSING_AGENT_COMMAND"
                )
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
            elif image_reference is not None:
                state = MealAgentState(
                    user_id=user_id,
                    thread_id=run.thread_id,
                    run_id=run.id,
                    graph_version=run.graph_version,
                    prompt_version=run.prompt_version,
                    tool_version=run.tool_version,
                    next_action=AgentNextAction.VISION,
                    vision_image=image_reference,
                    vision_request_key=f"{run.id.hex}-{image_reference.image_id.hex}",
                    vision_invocation_status="prepared",
                    status=AgentRuntimeStatus.ACCEPTED,
                )
                finished = await graph.ainvoke(state)
            else:
                return await self._fail_run(
                    run=run, user_id=user_id, code="CHECKPOINT_UNAVAILABLE"
                )
        except GraphRecursionError:
            return await self._fail_run(run=run, user_id=user_id, code="GRAPH_RECURSION_LIMIT")
        except Exception:
            # A failed provider/checkpoint call must never strand a run in "running".
            return await self._fail_run(run=run, user_id=user_id, code="RUNTIME_FAILURE")
        try:
            await self._persist_checkpoint(checkpointer=checkpointer, state=finished)
        except Exception:
            # The report is not resumable until its checkpoint is durable, so fail closed.
            return await self._fail_run(run=run, user_id=user_id, code="CHECKPOINT_PERSIST_FAILED")
        run = self._repository.get_run_for_user(run_id=run.id, user_id=user_id, for_update=True)
        assert run is not None
        self._sync_vision_invocation(state=finished, user_id=user_id)
        # A correction may create a new ledger run from an old thread checkpoint.  The state
        # counters deliberately remain cumulative for the safety limit, while each AgentRun must
        # record only work charged to that run; otherwise resumed model calls look duplicated.
        prior_budget = previous.budget if previous is not None else None
        run.graph_steps = max(
            run.graph_steps,
            finished.budget.graph_steps - (prior_budget.graph_steps if prior_budget else 0),
        )
        run.model_calls = max(
            run.model_calls,
            finished.budget.model_calls - (prior_budget.model_calls if prior_budget else 0),
        )
        run.tool_calls = max(
            run.tool_calls,
            finished.budget.tool_calls - (prior_budget.tool_calls if prior_budget else 0),
        )
        run.elapsed_ms = max(
            run.elapsed_ms,
            finished.budget.active_elapsed_ms - (prior_budget.active_elapsed_ms if prior_budget else 0),
        )
        run.estimated_cost_usd = max(
            run.estimated_cost_usd,
            finished.budget.estimated_cost_usd - (prior_budget.estimated_cost_usd if prior_budget else Decimal("0")),
        )
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
        if finished.status is AgentRuntimeStatus.LIMIT_REACHED:
            run.status = "limit_reached"
            run.failure_code = "LIMIT_REACHED"
            run.finished_at = run.updated_at
            self._commit_or_rollback()
            self.append_safe_event(
                thread_id=run.thread_id,
                user_id=user_id,
                run_id=run.id,
                event_type="failed",
                payload={"run_id": str(run.id), "failure_code": "LIMIT_REACHED"},
                safe_summary="分析已达到本次运行上限。",
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
        run.failure_code = (
            "OUTCOME_UNKNOWN"
            if finished.vision_invocation_status == "outcome_unknown"
            else "VISION_ANALYSIS_FAILED"
            if finished.vision_image is not None
            else "ANALYSIS_NOT_COMPLETED"
        )
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

    async def _fail_run(self, *, run: AgentRun, user_id: uuid.UUID, code: str) -> AgentRun:
        """Persist a stable failure category without exposing library/provider exception text."""

        run.status = "failed"
        run.failure_code = code
        run.finished_at = self._now()
        run.updated_at = run.finished_at
        self._commit_or_rollback()
        self.append_safe_event(
            thread_id=run.thread_id,
            user_id=user_id,
            run_id=run.id,
            event_type="failed",
            payload={"run_id": str(run.id), "failure_code": code},
            safe_summary="分析暂时无法完成，请稍后重试。",
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
        # This application keeps one latest resumable meal-analysis snapshot per thread.  The
        # saver orders arbitrary checkpoint IDs lexically, so a fresh `empty_checkpoint()` ID
        # can make an older waiting state look newer than a completed resume.  A stable thread
        # UUID turns this into an intentional upsert while the business ledger remains the
        # authority for ownership, audit and SSE.
        checkpoint["id"] = str(state.thread_id)
        checkpoint["channel_values"] = {"agent_state": state.model_dump(mode="json")}
        # Every persisted state is a new immutable blob version.  Reusing a version would leave
        # the checkpoint row pointing at an old waiting snapshot after a successful resume.
        state_version = uuid.uuid4().hex
        checkpoint["channel_versions"] = {"agent_state": state_version}
        await saver.aput(  # type: ignore[attr-defined]
            {
                "configurable": {
                    "thread_id": str(state.thread_id),
                    "checkpoint_ns": "meal-analysis",
                }
            },
            checkpoint,
            {"source": "loop", "step": 1, "parents": {}},
            {"agent_state": state_version},
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

    def record_validated_image(
        self,
        *,
        thread_id: uuid.UUID,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        reference: ValidatedImageReference,
    ) -> AgentImage:
        """Persist only an already-normalized image handle after proving tenant/run binding."""

        thread = self._repository.get_thread_for_user(
            thread_id=thread_id, user_id=user_id, for_update=True
        )
        run = self._repository.get_run_for_user(run_id=run_id, user_id=user_id, for_update=True)
        if thread is None or thread.deleted_at is not None or run is None or run.thread_id != thread_id:
            raise AgentThreadUnavailable("agent thread is unavailable")
        now = self._now()
        image = self._repository.add_image(
            AgentImage(
                id=uuid.uuid4(),
                thread_id=thread_id,
                run_id=run_id,
                user_id=user_id,
                digest_sha256=reference.digest_sha256,
                mime_type=reference.mime_type,
                width=reference.width,
                height=reference.height,
                byte_size=reference.byte_size,
                locator=reference.locator,
                status="ready",
                expires_at=reference.expires_at,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        self._commit_or_rollback()
        return image

    def get_image_reference(
        self, *, thread_id: uuid.UUID, image_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[AgentImage, ValidatedImageReference]:
        image = self._repository.get_image_for_thread_for_user(
            thread_id=thread_id, image_id=image_id, user_id=user_id
        )
        if image is None or image.deleted_at is not None or image.status not in {"ready", "processing"}:
            raise AgentThreadUnavailable("agent image is unavailable")
        return image, ValidatedImageReference(
            digest_sha256=image.digest_sha256,
            mime_type=image.mime_type,  # type: ignore[arg-type]
            width=image.width,
            height=image.height,
            byte_size=image.byte_size,
            locator=image.locator,
            created_at=image.created_at,
            expires_at=image.expires_at,
        )

    def get_image_for_run(self, *, run_id: uuid.UUID, user_id: uuid.UUID) -> AgentImage | None:
        """Expose an existing opaque image record only after the run's tenant check."""

        if self._repository.get_run_for_user(run_id=run_id, user_id=user_id) is None:
            raise AgentThreadUnavailable("agent run is unavailable")
        return self._repository.get_image_for_run_for_user(run_id=run_id, user_id=user_id)

    def images_for_thread_cleanup(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[tuple[AgentImage, ValidatedImageReference], ...]:
        # Pending user deletion deliberately hides the thread from public reads. Cleanup still
        # needs the same tenant-filtered records before the FK cascade removes their handles.
        images = self._repository.list_images_for_thread_for_user(
            thread_id=thread_id, user_id=user_id
        )
        return tuple((image, _image_reference(image)) for image in images)

    def image_for_cleanup(
        self, *, image_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[AgentImage, ValidatedImageReference] | None:
        image = self._repository.get_image_for_user(image_id=image_id, user_id=user_id)
        if image is None or image.deleted_at is not None:
            return None
        return image, _image_reference(image)

    def prepare_vision_invocation(
        self,
        *,
        image_id: uuid.UUID,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        request_key: str,
        model_alias: str,
    ) -> AgentVisionInvocation:
        """Create/reuse a safe invocation record; unknown outcomes are never reset here."""

        image = self._repository.get_image_for_user(image_id=image_id, user_id=user_id, for_update=True)
        run = self._repository.get_run_for_user(run_id=run_id, user_id=user_id, for_update=True)
        if image is None or run is None or image.run_id != run_id or image.thread_id != run.thread_id:
            raise AgentThreadUnavailable("agent image is unavailable")
        existing = self._repository.get_vision_invocation_for_image_for_update(
            image_id=image_id, user_id=user_id, request_key=request_key
        )
        if existing is not None:
            return existing
        now = self._now()
        invocation = self._repository.add_vision_invocation(
            AgentVisionInvocation(
                id=uuid.uuid4(),
                image_id=image_id,
                thread_id=image.thread_id,
                run_id=run_id,
                user_id=user_id,
                request_key=request_key,
                model_alias=model_alias,
                provider_request_id=None,
                status="prepared",
                attempt=0,
                cost_cny=Decimal("0"),
                safe_result_digest=None,
                failure_code=None,
                created_at=now,
                updated_at=now,
            )
        )
        image.status = "processing"
        image.updated_at = now
        self._commit_or_rollback()
        return invocation

    def mark_image_deleted(self, *, image_id: uuid.UUID, user_id: uuid.UUID) -> AgentImage:
        """Record a completed filesystem deletion; callers perform the irreversible I/O first."""

        image = self._repository.get_image_for_user(image_id=image_id, user_id=user_id, for_update=True)
        if image is None:
            raise AgentThreadUnavailable("agent image is unavailable")
        now = self._now()
        image.status = "deleted"
        image.deleted_at = now
        image.updated_at = now
        self._commit_or_rollback()
        return image

    def mark_image_deletion_failed(self, *, image_id: uuid.UUID, user_id: uuid.UUID) -> AgentImage:
        """Keep a retryable lifecycle record when filesystem deletion could not be confirmed."""

        image = self._repository.get_image_for_user(image_id=image_id, user_id=user_id, for_update=True)
        if image is None:
            raise AgentThreadUnavailable("agent image is unavailable")
        image.status = "delete_failed"
        image.updated_at = self._now()
        self._commit_or_rollback()
        return image

    def _sync_vision_invocation(self, *, state: MealAgentState, user_id: uuid.UUID) -> None:
        """Persist only the completed safe invocation envelope after its checkpoint is durable."""

        if state.vision_image is None or not state.vision_request_key:
            return
        invocation = self._repository.get_vision_invocation_for_image_for_update(
            image_id=state.vision_image.image_id,
            user_id=user_id,
            request_key=state.vision_request_key,
        )
        if invocation is None:
            return
        now = self._now()
        invocation.status = state.vision_invocation_status or "failed"
        invocation.attempt = max(invocation.attempt, state.vision_attempts, 1)
        invocation.updated_at = now
        if state.vision_metadata is not None:
            invocation.model_alias = state.vision_metadata.model_alias
            invocation.provider_request_id = state.vision_metadata.provider_request_id
            invocation.cost_cny = state.vision_metadata.cost_cny
            invocation.safe_result_digest = hashlib.sha256(
                json.dumps(
                    [item.model_dump(mode="json") for item in state.items],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        elif invocation.status == "outcome_unknown":
            invocation.failure_code = "PROVIDER_OUTCOME_UNKNOWN"
        else:
            invocation.failure_code = "VISION_PROVIDER_FAILURE"
        self._commit_or_rollback()

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

    def request_thread_deletion(
        self,
        *,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        policy: RetentionPolicy,
    ) -> AgentDeletionIntent:
        """Persist an idempotent deletion deadline before a worker can act on it."""

        thread = self._repository.get_thread_for_user(
            thread_id=thread_id, user_id=user_id, for_update=True
        )
        if thread is None:
            raise AgentThreadUnavailable("agent thread is unavailable")
        existing = self._repository.get_deletion_intent_for_thread_for_user(
            thread_id=thread_id, user_id=user_id, for_update=True
        )
        if existing is not None:
            return existing
        requested_at = self._now()
        thread.status = "deleted"
        thread.deleted_at = requested_at
        thread.revision += 1
        intent = self._repository.add_deletion_intent(
            AgentDeletionIntent(
                id=uuid.uuid4(),
                thread_id=thread_id,
                user_id=user_id,
                status="pending",
                requested_at=requested_at,
                # Leave one bounded scheduler interval before the externally visible 24h SLA.
                purge_after=requested_at + policy.deletion_due_delta,
                completed_at=None,
            )
        )
        self._commit_or_rollback()
        return intent

    def retention_sweep(self, *, policy: RetentionPolicy) -> RetentionSweep:
        """Select exactly scoped expired records; callers own saver I/O and process leasing."""

        now = self._now()
        due_deletions = tuple(
            (intent.thread_id, intent.user_id)
            for intent in self._repository.list_due_deletion_intents(due_at=now)
        )
        inactive_threads = tuple(
            (thread.id, thread.user_id)
            for thread in self._repository.list_threads_inactive_before(
                cutoff=now - timedelta(days=policy.checkpoint_event_days)
            )
        )
        expired_runs = tuple(
            (run.id, run.user_id)
            for run in self._repository.list_runs_updated_before(
                cutoff=now - timedelta(days=policy.audit_days)
            )
        )
        expired_images = tuple(
            (image.id, image.user_id)
            for image in self._repository.list_images_expiring_before(cutoff=now)
        )
        candidates = [
            self._repository.earliest_pending_deletion_at(),
            _add_days(self._repository.earliest_thread_activity_at(), policy.checkpoint_event_days),
            _add_days(self._repository.earliest_run_updated_at(), policy.audit_days),
            self._repository.earliest_image_expiry_at(),
        ]
        return RetentionSweep(
            due_deletions=due_deletions,
            inactive_threads=inactive_threads,
            expired_runs=expired_runs,
            expired_images=expired_images,
            next_eligible_at=min((item for item in candidates if item is not None), default=None),
        )

    def finalize_thread_deletion(self, *, thread_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete only the exact tenant/thread after its saver namespace is gone."""

        deleted = self._repository.delete_thread_for_user(thread_id=thread_id, user_id=user_id)
        self._commit_or_rollback()
        return deleted

    def purge_expired_thread_events(self, *, thread_id: uuid.UUID, user_id: uuid.UUID) -> int:
        deleted = self._repository.delete_events_for_thread_for_user(
            thread_id=thread_id, user_id=user_id
        )
        self._commit_or_rollback()
        return deleted

    def purge_expired_run(self, *, run_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        deleted = self._repository.delete_run_for_user(run_id=run_id, user_id=user_id)
        self._commit_or_rollback()
        return deleted

    def _commit_or_rollback(self) -> None:
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise


def _add_days(value: datetime | None, days: int) -> datetime | None:
    return value + timedelta(days=days) if value is not None else None


def _image_reference(image: AgentImage) -> ValidatedImageReference:
    return ValidatedImageReference(
        digest_sha256=image.digest_sha256,
        mime_type=image.mime_type,  # type: ignore[arg-type]
        width=image.width,
        height=image.height,
        byte_size=image.byte_size,
        locator=image.locator,
        created_at=image.created_at,
        expires_at=image.expires_at,
    )
