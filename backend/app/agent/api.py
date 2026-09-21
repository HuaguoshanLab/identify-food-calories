"""Authenticated Agent API backed by a tenant-filtered event ledger.

Routes own HTTP presentation only. AgentService owns ownership/idempotency and the graph sees
only its provider/tool ports; SSE merely replays safe persisted events and never drives a run.
"""

from __future__ import annotations

from app.core.logging import current_request_id, observed

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator, Generator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.exc import OperationalError

from app.agent.graph import AgentRuntime
from app.agent.models import AgentRun
from app.agent.repository import SqlAlchemyAgentRepository
from app.agent.schemas import (
    AgentCommandAcceptedResponse,
    AgentDeletionAcceptedResponse,
    AgentErrorResponse,
    AgentImageAcceptedResponse,
    AgentInputRequest,
    DietPlanningStartCommand,
    AgentThreadCreateRequest,
    AgentThreadSnapshot,
    AgentThreadStatus,
    SafeStreamStage,
    SafeStreamStageEvent,
)
from app.agent.service import AgentRuntimeAdmissionDenied, DIET_PLANNING_GRAPH_VERSION, AgentCommandConflict, AgentLeaseUnavailable, AgentService, AgentThreadUnavailable, PersistedAgentGraph, RetentionPolicy, safe_meal_stream_stage
from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.service import AdminService
from app.agent.state import AgentGraphKind, StateImageReference
from app.agent.supervisor import PostgresLeaseSupervisor
from app.agent.weight import InvalidWeightInput
from app.images.schemas import ImageValidationError, ValidatedImageReference
from app.images.service import ImageSafetyService
from app.auth.api import AuthenticatedPrincipal
from app.planning.service import safe_planning_stream_stage
from app.planning.repository import SqlAlchemyPlanningProfileRepository
from app.planning.service import PlanningCompletionProjectionService
from app.planning.archive_repository import SqlAlchemyPlanArchiveRepository
from app.planning.archive_service import PlanArchiveService, PlanArchiveConflict

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": AgentErrorResponse, "description": "Bearer authentication failed."},
    status.HTTP_404_NOT_FOUND: {"model": AgentErrorResponse, "description": "Thread is unavailable."},
    status.HTTP_409_CONFLICT: {"model": AgentErrorResponse, "description": "Command conflicts."},
}


AgentPrincipal = AuthenticatedPrincipal


def _safe_stream_event(event: object) -> str | None:
    """Project an event through the closed DTO, never its payload, run, or graph state."""

    event_type = getattr(event, "event_type", None)
    summary = getattr(event, "safe_summary", None)
    if not isinstance(event_type, str) or not isinstance(summary, str):
        return None
    stage = safe_meal_stream_stage(event_type) or safe_planning_stream_stage(event_type)
    if stage is None:
        return None
    return SafeStreamStageEvent(stage=SafeStreamStage(stage), message=summary).model_dump_json()


def _runtime(request: Request) -> AgentRuntime:
    runtime = cast(AgentRuntime | None, getattr(request.app.state, "agent_runtime", None))
    if runtime is None:
        raise HTTPException(status_code=503, detail="Agent runtime is unavailable.")
    return runtime


def get_agent_service(request: Request) -> Generator[AgentService, None, None]:
    """Use the lifecycle-selected DB target; test mode never falls back to DATABASE_URL."""

    session = cast(Any, _runtime(request).session_factory())
    try:
        yield _build_agent_service(session)
    finally:
        session.close()


def _build_agent_service(session: Any) -> AgentService:
    return AgentService(
        repository=SqlAlchemyAgentRepository(session),
        commit=session.commit,
        rollback=session.rollback,
        planning_archive_writer=PlanArchiveService(
            repository=SqlAlchemyPlanArchiveRepository(session)
        ),
        planning_completion_writer=PlanningCompletionProjectionService(
            repository=SqlAlchemyPlanningProfileRepository(session)
        ),
        runtime_config_admitter=AdminService(
            repository=SqlAlchemyAdminRepository(session),
            now=lambda: datetime.now(UTC),
        ),
    )


def _status(run_status: str | None) -> AgentThreadStatus:
    return {
        "accepted": AgentThreadStatus.PARTIAL, "running": AgentThreadStatus.PARTIAL,
        "waiting_input": AgentThreadStatus.WAITING, "completed": AgentThreadStatus.COMPLETED,
        "failed": AgentThreadStatus.RETRYABLE, "limit_reached": AgentThreadStatus.TERMINAL,
    }.get(run_status or "", AgentThreadStatus.PARTIAL)


def _snapshot(service: AgentService, *, thread_id: uuid.UUID, user_id: uuid.UUID) -> AgentThreadSnapshot:
    thread, run, events = service.latest_run_and_events(thread_id=thread_id, user_id=user_id)
    report: dict[str, object] | None = None
    for event in reversed(events):
        candidate = event.payload.get("report")
        if event.event_type in {
            "completed",
            "completed_validated",
            "waiting_input",
            "complete",
            "needs_input",
            "retryable",
            "terminal",
        } and isinstance(candidate, dict):
            report = candidate
            break
    return AgentThreadSnapshot(
        thread_id=thread.id,
        status=_status(run.status if run else None),
        revision=thread.revision,
        report=report,
        recovery_code=run.failure_code if run is not None else None,
    )


def _command_hash(text: str) -> dict[str, object]:
    # Durable idempotency contains a digest, never a meal description.
    return {"kind": "description", "input_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def _image_command_hash(reference: ValidatedImageReference) -> dict[str, object]:
    return {"kind": "image", "digest_sha256": reference.digest_sha256}


def _image_state(*, image_id: uuid.UUID, reference: ValidatedImageReference) -> StateImageReference:
    return StateImageReference(
        image_id=image_id,
        digest_sha256=reference.digest_sha256,
        mime_type=reference.mime_type,
        width=reference.width,
        height=reference.height,
        byte_size=reference.byte_size,
        locator=reference.locator,
        created_at=reference.created_at,
        expires_at=reference.expires_at,
        status="ready",
    )


@observed("agent", execution=True)
async def _execute(
    *,
    service: AgentService,
    runtime: AgentRuntime,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    text: str | None = None,
    image_reference: StateImageReference | None = None,
    resume_payload: dict[str, object] | None = None,
    planning_command: DietPlanningStartCommand | None = None,
    graph_kind: AgentGraphKind = AgentGraphKind.MEAL_ANALYSIS,
) -> None:
    from app.core.tracing import DisabledTracingRuntime

    tracing = getattr(runtime, "tracing", DisabledTracingRuntime())
    with tracing.span(
        "agent.run",
        {
            "node.name": graph_kind.value,
            "thread.fingerprint": tracing.scoped_hmac(str(run_id)),
        },
    ) as trace_span:
        if trace_span is not None:
            trace_span.update(
                input={
                    "kind": (
                        "text" if text is not None else "image" if image_reference is not None
                        else "resume" if resume_payload is not None else "diet_planning"
                    ),
                }
            )
        # The supervisor owns its Session; a database lock wait must not block HTTP dispatch.
        supervisor = cast(PostgresLeaseSupervisor, runtime.supervisor)
        try:
            lease = await asyncio.to_thread(
                supervisor.claim, run_id=run_id, user_id=user_id
            )
        except OperationalError as error:
            raise HTTPException(status_code=503, detail="Agent execution is temporarily busy.") from error
        try:
            graph = cast(PersistedAgentGraph, runtime.graph.for_kind(graph_kind))
            completed_run = await service.execute_run(
                run_id=run_id,
                user_id=user_id,
                graph=graph,
                input_text=text,
                image_reference=image_reference,
                resume_payload=resume_payload,
                planning_command=planning_command,
                graph_kind=graph_kind,
            )
        finally:
            await asyncio.to_thread(
                supervisor.release,
                run_id=run_id,
                user_id=user_id,
                holder_id=lease.holder_id,
            )
        if completed_run is not None:
            import logging
            logging.getLogger(__name__).info("", extra={"event": "agent_result", "status": completed_run.status})
        if trace_span is not None and completed_run is not None:
            trace_span.update(
                output={
                    "status": completed_run.status,
                    "model_calls": completed_run.model_calls,
                    "tool_calls": completed_run.tool_calls,
                    "elapsed_ms": completed_run.elapsed_ms,
                }
            )


async def _execute_detached(
    *,
    runtime: AgentRuntime,
    cleanup_reference: ValidatedImageReference | None = None,
    cleanup_image_id: uuid.UUID | None = None,
    **command: Any,
) -> None:
    """Execute with a fresh transaction boundary after the HTTP request has returned."""

    session = cast(Any, runtime.session_factory())
    service = _build_agent_service(session)
    try:
        try:
            await _execute(service=service, runtime=runtime, **command)
        except AgentLeaseUnavailable:
            # A duplicate dispatch found the original attempt still running. It must not
            # overwrite that attempt's eventual result with a synthetic failure.
            return
        except Exception:
            await service.fail_dispatched_run(
                run_id=cast(uuid.UUID, command["run_id"]),
                user_id=cast(uuid.UUID, command["user_id"]),
                code="DISPATCH_EXECUTION_FAILED",
            )
            raise
    finally:
        if cleanup_reference is not None and cleanup_image_id is not None:
            safety = cast(ImageSafetyService, runtime.image_safety)
            try:
                safety.delete(cleanup_reference)
                service.mark_image_deleted(
                    image_id=cleanup_image_id, user_id=cast(uuid.UUID, command["user_id"])
                )
            except Exception:
                service.mark_image_deletion_failed(
                    image_id=cleanup_image_id, user_id=cast(uuid.UUID, command["user_id"])
                )
        session.close()


def _dispatch(runtime: AgentRuntime, **command: Any) -> None:
    cast(PostgresLeaseSupervisor, runtime.supervisor).submit_execution(
        _execute_detached(runtime=runtime, **command)
    )


async def _start_execution(
    *, request: Request, service: AgentService, runtime: AgentRuntime, **command: Any
) -> None:
    """Honor the standard async preference while retaining a synchronous API fallback."""

    preferences = {
        item.strip().casefold()
        for item in request.headers.get("prefer", "").split(",")
        if item.strip()
    }
    if "respond-async" in preferences:
        _dispatch(runtime, **command)
        return
    await _execute(service=service, runtime=runtime, **command)


@router.post("/threads", operation_id="createAgentThread", response_model=AgentThreadSnapshot, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES)
async def create_agent_thread(payload: AgentThreadCreateRequest, request: Request, principal: AgentPrincipal, service: AgentService = Depends(get_agent_service)) -> AgentThreadSnapshot | JSONResponse:
    thread = service.create_thread(user_id=principal)
    try:
        run = service.create_or_reuse_run(thread_id=thread.id, user_id=principal, command_key=f"initial-{uuid.uuid4()}", canonical_command=_command_hash(payload.input_text))
    except AgentRuntimeAdmissionDenied:
        return _runtime_admission_rejected()
    runtime = _runtime(request)
    await _start_execution(
        request=request, service=service, runtime=runtime,
        run_id=run.id, user_id=principal, text=payload.input_text,
    )
    return _snapshot(service, thread_id=thread.id, user_id=principal)


@router.post(
    "/threads/diet-planning",
    operation_id="createDietPlanningThread",
    response_model=AgentThreadSnapshot,
    status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES,
)
async def create_diet_planning_thread(
    payload: DietPlanningStartCommand,
    request: Request,
    principal: AgentPrincipal,
    command_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    service: AgentService = Depends(get_agent_service),
) -> AgentThreadSnapshot | JSONResponse:
    """Start one owned planning thread; the key deterministically reuses its ledger command."""

    thread_id = uuid.uuid5(uuid.NAMESPACE_URL, f"food-agent:diet-planning:{principal}:{command_key}")
    try:
        thread = service.create_thread(user_id=principal, thread_id=thread_id)
        run = service.create_or_reuse_run(
            thread_id=thread.id,
            user_id=principal,
            command_key=command_key,
            canonical_command={"kind": "diet_planning", "command": payload.model_dump(mode="json")},
            graph_kind=AgentGraphKind.DIET_PLANNING,
        )
        if run.status != "completed":
            runtime = _runtime(request)
            await _start_execution(
                request=request, service=service, runtime=runtime,
                run_id=run.id,
                user_id=principal,
                planning_command=payload,
                graph_kind=AgentGraphKind.DIET_PLANNING,
            )
    except PlanArchiveConflict as error:
        return _error(status.HTTP_409_CONFLICT, "PLAN_ARCHIVE_CONFLICT", str(error))
    except AgentCommandConflict:
        return _error(status.HTTP_409_CONFLICT, "COMMAND_KEY_CONFLICT", "该请求标识已用于不同计划命令。")
    except AgentRuntimeAdmissionDenied:
        return _runtime_admission_rejected()
    return _snapshot(service, thread_id=thread.id, user_id=principal)


@router.post(
    "/threads/image",
    operation_id="createAgentImageThread",
    response_model=AgentThreadSnapshot,
    status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES,
)
async def create_agent_image_thread(
    principal: AgentPrincipal, service: AgentService = Depends(get_agent_service)
) -> AgentThreadSnapshot:
    """Create an owned empty thread so image upload never needs a fabricated text command."""

    thread = service.create_thread(user_id=principal)
    return _snapshot(service, thread_id=thread.id, user_id=principal)


@router.post(
    "/threads/{thread_id}/images",
    operation_id="uploadAgentMealImage",
    response_model=AgentImageAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERROR_RESPONSES,
)
async def upload_agent_meal_image(
    thread_id: uuid.UUID,
    request: Request,
    principal: AgentPrincipal,
    command_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
    image: UploadFile = File(...),
    service: AgentService = Depends(get_agent_service),
) -> AgentImageAcceptedResponse | JSONResponse:
    """Validate a bounded multipart image after ownership, then erase its temporary handle."""

    try:
        service.get_thread(thread_id=thread_id, user_id=principal)
    except AgentThreadUnavailable:
        raise _unavailable() from None
    runtime = _runtime(request)
    settings = request.app.state.settings
    try:
        # Read one byte beyond the declared limit; never materialize an unbounded request body.
        content = await image.read(settings.image_max_bytes + 1)
        safety = cast(ImageSafetyService, runtime.image_safety)
        reference = safety.validate_and_store(content=content, declared_mime=image.content_type)
    except ImageValidationError as error:
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, error.code, error.safe_message)
    finally:
        await image.close()

    try:
        run = service.create_or_reuse_run(
            thread_id=thread_id,
            user_id=principal,
            command_key=command_key,
            canonical_command=_image_command_hash(reference),
        )
        existing_image = service.get_image_for_run(run_id=run.id, user_id=principal)
        if existing_image is not None:
            # The caller retried an accepted command. Its newly normalized temporary file is
            # unnecessary and must not create a second paid invocation or durable image row.
            safety.delete(reference)
            return AgentImageAcceptedResponse(
                thread_id=thread_id,
                image_id=existing_image.id,
                status=_status(run.status),
            )
        image_record = service.record_validated_image(
            thread_id=thread_id, run_id=run.id, user_id=principal, reference=reference
        )
        image_state = _image_state(image_id=image_record.id, reference=reference)
        service.prepare_vision_invocation(
            image_id=image_record.id,
            run_id=run.id,
            user_id=principal,
            request_key=f"{run.id.hex}-{image_record.id.hex}",
            model_alias=settings.qwen_model or "fake-vision-v1",
        )
        if "respond-async" in request.headers.get("prefer", "").casefold():
            _dispatch(
                runtime, run_id=run.id, user_id=principal,
                image_reference=image_state, cleanup_reference=reference,
                cleanup_image_id=image_record.id,
            )
        else:
            await _execute(
                service=service, runtime=runtime, run_id=run.id,
                user_id=principal, image_reference=image_state,
            )
            try:
                safety.delete(reference)
                service.mark_image_deleted(image_id=image_record.id, user_id=principal)
            except Exception:
                service.mark_image_deletion_failed(
                    image_id=image_record.id, user_id=principal
                )
    except PlanArchiveConflict as error:
        return _error(status.HTTP_409_CONFLICT, "PLAN_ARCHIVE_CONFLICT", str(error))
    except AgentCommandConflict:
        safety.delete(reference)
        return _error(status.HTTP_409_CONFLICT, "COMMAND_KEY_CONFLICT", "该请求标识已用于不同图片。")
    except AgentRuntimeAdmissionDenied:
        safety.delete(reference)
        return _runtime_admission_rejected()
    except Exception:
        safety.delete(reference)
        raise
    return AgentImageAcceptedResponse(
        thread_id=thread_id,
        image_id=image_record.id,
        status=_status(run.status),
    )


@router.post("/threads/{thread_id}/input", operation_id="submitAgentInput", response_model=AgentCommandAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, responses={**_ERROR_RESPONSES, 422: {"model": AgentErrorResponse, "description": "Invalid weight input; existing analysis remains unchanged."}})
async def submit_agent_input(
    thread_id: uuid.UUID,
    payload: AgentInputRequest,
    request: Request,
    principal: AgentPrincipal,
    command_key: Annotated[str | None, Header(alias="Idempotency-Key", min_length=1, max_length=128)] = None,
    service: AgentService = Depends(get_agent_service),
) -> AgentCommandAcceptedResponse | JSONResponse:
    try:
        _thread, latest, _events = service.latest_run_and_events(thread_id=thread_id, user_id=principal)
    except AgentThreadUnavailable:
        raise _unavailable() from None
    runtime = _runtime(request)
    planning_thread = latest is not None and latest.graph_version == DIET_PLANNING_GRAPH_VERSION
    # Existing clients without a key retain legacy replay behaviour. New clients
    # identify a submission, so identical wording can represent a later adjustment.
    planning_key = (
        f"planning-submission-{hashlib.sha256(command_key.encode('utf-8')).hexdigest()}"
        if command_key is not None else
        f"planning-adjustment-{hashlib.sha256(payload.text.encode('utf-8')).hexdigest()[:32]}"
    )
    if planning_thread:
        try:
            existing = service.find_reusable_run(
                thread_id=thread_id, user_id=principal, command_key=planning_key,
                canonical_command={"kind": "planning_adjustment", "input_hash": hashlib.sha256(payload.text.encode("utf-8")).hexdigest()},
            )
        except AgentCommandConflict:
            return _error(status.HTTP_409_CONFLICT, "COMMAND_KEY_CONFLICT", "该请求标识已用于不同调整，请刷新计划后重新提交。")
        except AgentThreadUnavailable:
            raise _unavailable() from None
        if existing is not None:
            return AgentCommandAcceptedResponse(thread_id=thread_id, status=_status(existing.status))
    try:
        resume_payload = await service.resume_payload_for_text(
            graph=cast(
                PersistedAgentGraph,
                runtime.graph.for_kind(
                    AgentGraphKind.DIET_PLANNING
                    if planning_thread
                    else AgentGraphKind.MEAL_ANALYSIS
                ),
            ),
            thread_id=thread_id,
            text=payload.text,
            graph_kind=AgentGraphKind.DIET_PLANNING if planning_thread else AgentGraphKind.MEAL_ANALYSIS,
        )
    except InvalidWeightInput as error:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "INVALID_WEIGHT", str(error))
    try:
        return await _submit_agent_input_after_admission(
            thread_id=thread_id, payload=payload, request=request,
            principal=principal, service=service,
            runtime=runtime, latest=latest, planning_thread=planning_thread, resume_payload=resume_payload,
            planning_key=planning_key,
        )
    except AgentCommandConflict:
        return _error(status.HTTP_409_CONFLICT, "COMMAND_KEY_CONFLICT", "该请求标识已用于不同调整，请刷新计划后重新提交。")
    except PlanArchiveConflict as error:
        return _error(status.HTTP_409_CONFLICT, "PLAN_ARCHIVE_CONFLICT", str(error))
    except AgentRuntimeAdmissionDenied:
        return _runtime_admission_rejected()


async def _submit_agent_input_after_admission(
    *,
    thread_id: uuid.UUID,
    payload: AgentInputRequest,
    request: Request,
    principal: AgentPrincipal,
    service: AgentService,
    runtime: AgentRuntime,
    latest: AgentRun | None,
    planning_thread: bool,
    resume_payload: dict[str, object] | None,
    planning_key: str,
) -> AgentCommandAcceptedResponse | JSONResponse:
    """Keep admission failures at the HTTP boundary while AgentService owns creation."""

    if planning_thread:
        assert latest is not None
        if resume_payload is None:
            return AgentCommandAcceptedResponse(thread_id=thread_id, status=_status(latest.status))
        run = service.create_or_reuse_run(
            thread_id=thread_id,
            user_id=principal,
            command_key=planning_key,
            canonical_command={"kind": "planning_adjustment", "input_hash": hashlib.sha256(payload.text.encode("utf-8")).hexdigest()},
            graph_kind=AgentGraphKind.DIET_PLANNING,
        )
        if run.status == "accepted":
            await _start_execution(
                request=request, service=service, runtime=runtime,
                run_id=run.id,
                user_id=principal,
                resume_payload=resume_payload,
                graph_kind=AgentGraphKind.DIET_PLANNING,
            )
        return AgentCommandAcceptedResponse(thread_id=thread_id, status=_status(run.status))
    if latest is not None and latest.status == "waiting_input":
        if resume_payload is None:
            return AgentCommandAcceptedResponse(thread_id=thread_id, status=AgentThreadStatus.WAITING)
        run = latest
        await _start_execution(
            request=request, service=service, runtime=runtime,
            run_id=run.id,
            user_id=principal,
            resume_payload=resume_payload,
        )
        return AgentCommandAcceptedResponse(thread_id=thread_id, status=_status(run.status))
    if latest is not None and latest.status == "completed":
        if resume_payload is None or "corrections" not in resume_payload:
            return _error(
                status.HTTP_409_CONFLICT,
                "CORRECTION_REQUIRES_TARGET",
                "已完成分析只能提交针对既有项目的修正；新餐请创建新会话。",
            )
        run = service.create_or_reuse_run(
            thread_id=thread_id,
            user_id=principal,
            command_key=f"correction-{uuid.uuid4()}",
            canonical_command=_command_hash(payload.text),
        )
        await _start_execution(
            request=request, service=service, runtime=runtime,
            run_id=run.id,
            user_id=principal,
            resume_payload=resume_payload,
        )
        return AgentCommandAcceptedResponse(thread_id=thread_id, status=_status(run.status))
    run = service.create_or_reuse_run(
        thread_id=thread_id,
        user_id=principal,
        command_key=f"input-{uuid.uuid4()}",
        canonical_command=_command_hash(payload.text),
    )
    await _start_execution(
        request=request, service=service, runtime=runtime,
        run_id=run.id, user_id=principal, text=payload.text,
    )
    return AgentCommandAcceptedResponse(thread_id=thread_id, status=_status(run.status))


@router.get("/threads/{thread_id}", operation_id="getAgentThread", response_model=AgentThreadSnapshot, responses=_ERROR_RESPONSES)
def get_agent_thread(thread_id: uuid.UUID, principal: AgentPrincipal, service: AgentService = Depends(get_agent_service)) -> AgentThreadSnapshot:
    try:
        return _snapshot(service, thread_id=thread_id, user_id=principal)
    except AgentThreadUnavailable:
        raise _unavailable() from None


@router.get("/threads/{thread_id}/events", operation_id="streamAgentEvents", response_model=None, responses={status.HTTP_200_OK: {"description": "Server-sent Agent events.", "content": {"text/event-stream": {"schema": {"type": "string"}}}}, **_ERROR_RESPONSES})
def stream_agent_events(thread_id: uuid.UUID, request: Request, principal: AgentPrincipal, service: AgentService = Depends(get_agent_service)) -> StreamingResponse:
    try:
        after_seq = max(int(request.headers.get("last-event-id", "0")), 0)
        _thread, _run, events = service.latest_run_and_events(thread_id=thread_id, user_id=principal, after_seq=after_seq)
    except (AgentThreadUnavailable, ValueError):
        raise _unavailable() from None

    runtime = _runtime(request)

    def read_followup(sequence: int):
        """Own the synchronous Session inside its worker thread."""
        session = cast(Any, runtime.session_factory())
        try:
            return _build_agent_service(session).latest_run_and_events(
                thread_id=thread_id, user_id=principal, after_seq=sequence
            )
        finally:
            session.close()

    async def replay_and_follow() -> AsyncIterator[str]:
        sequence = after_seq
        pending = events
        while True:
            for event in pending:
                sequence = max(sequence, event.seq)
                body = _safe_stream_event(event)
                if body is not None:
                    yield f"id: {event.seq}\nevent: agent\ndata: {body}\n\n"
            if await request.is_disconnected():
                return
            _thread, run, pending = await asyncio.to_thread(read_followup, sequence)
            terminal = run is None or run.status in {
                "waiting_input", "completed", "failed", "limit_reached"
            }
            if pending:
                continue
            if terminal:
                return
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(
        replay_and_follow(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/threads/{thread_id}/retry", operation_id="retryAgentRun", response_model=AgentCommandAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES)
def retry_agent_run(
    thread_id: uuid.UUID,
    principal: AgentPrincipal,
    service: AgentService = Depends(get_agent_service),
) -> JSONResponse:
    try:
        service.get_thread(thread_id=thread_id, user_id=principal)
    except AgentThreadUnavailable:
        raise _unavailable() from None
    return _error(status.HTTP_409_CONFLICT, "RETRY_REQUIRES_INPUT", "请重新提交餐食描述。")


@router.delete("/threads/{thread_id}", operation_id="deleteAgentThread", response_model=AgentDeletionAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES)
def delete_agent_thread(
    thread_id: uuid.UUID,
    request: Request,
    principal: AgentPrincipal,
    service: AgentService = Depends(get_agent_service),
) -> AgentDeletionAcceptedResponse:
    """Persist the bounded deletion deadline before waking the lifespan-owned worker."""

    settings = request.app.state.settings
    try:
        intent = service.request_thread_deletion(
            thread_id=thread_id,
            user_id=principal,
            policy=RetentionPolicy(
                checkpoint_event_days=settings.retention_checkpoint_event_days,
                audit_days=settings.retention_audit_days,
                deletion_due_delta=settings.retention_deletion_due_delta,
                poll_interval=timedelta(seconds=settings.retention_poll_interval_seconds),
            ),
        )
    except AgentThreadUnavailable:
        raise _unavailable() from None
    worker = cast(PostgresLeaseSupervisor, _runtime(request).supervisor).retention_worker
    if worker is None:
        raise HTTPException(status_code=503, detail="Agent retention runtime is unavailable.")
    worker.wake()
    return AgentDeletionAcceptedResponse(thread_id=thread_id, due_at=intent.purge_after)


def _unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent thread is unavailable.")


def _runtime_admission_rejected() -> JSONResponse:
    """Do not reveal whether a provider is disabled, capped, or unconfigured."""

    return _error(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "AGENT_RUNTIME_UNAVAILABLE",
        "当前分析服务暂不可用，请稍后重试。",
    )


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "request_id": current_request_id()}})
