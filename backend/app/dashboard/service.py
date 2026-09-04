"""Dashboard read use cases over snapshot facts and a narrow completion-target port."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.dashboard.ports import DashboardTimezone, PlanningCompletionTargetPort
from app.dashboard.schemas import (
    DashboardDaySummary,
    DashboardHistoryCursor,
    DashboardHistoryGroup,
    DashboardHistoryItem,
    DashboardHistoryPage,
    DashboardHistoryRecord,
    DashboardNutritionTotals,
    DashboardOverview,
    WeeklyReviewPublicResponse,
)
from app.dashboard.weekly_review_dto import WeeklyReviewCacheKey, WeeklyReviewFacts, WeeklyReviewResponse


class DashboardAggregate(Protocol):
    @property
    def consumed_local_date(self) -> date: ...

    @property
    def totals(self) -> DashboardNutritionTotals: ...

    @property
    def meal_count(self) -> int: ...


class DashboardRepository(Protocol):
    def get_dashboard_timezone_for_user(self, *, user_id: uuid.UUID) -> DashboardTimezone | None: ...
    def get_daily_aggregates(self, *, user_id: uuid.UUID, start_date: date, end_date: date) -> Sequence[DashboardAggregate]: ...
    def get_history_page(self, *, user_id: uuid.UUID, cursor: DashboardHistoryCursor | None, limit: int) -> Sequence[DashboardHistoryRecord]: ...


class InvalidDashboardCursor(ValueError):
    """Raised before a malformed or modified cursor can reach the repository."""


class DashboardTimezonePreconditionError(ValueError):
    """The user must confirm a valid statistical basis before dashboard aggregation."""


class WeeklyReviewWeekStartInvalid(ValueError):
    """A weekly-review window is neither a Monday nor a completed/current local week."""


class DashboardCursorCodec:
    """Signs keyset positions so clients cannot alter dates, timestamps, or UUID ties."""

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def encode(self, cursor: DashboardHistoryCursor) -> str:
        payload = json.dumps(cursor.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return _b64encode(payload) + "." + _b64encode(signature)

    def decode(self, value: str) -> DashboardHistoryCursor:
        try:
            encoded_payload, encoded_signature = value.split(".", 1)
            payload, signature = _b64decode(encoded_payload), _b64decode(encoded_signature)
            expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("signature mismatch")
            return DashboardHistoryCursor.model_validate_json(payload)
        except (TypeError, ValueError) as error:
            raise InvalidDashboardCursor("dashboard cursor is invalid") from error


class DashboardService:
    def __init__(
        self,
        *,
        repository: DashboardRepository,
        target_port: PlanningCompletionTargetPort,
        now: Callable[[], datetime] | None = None,
        cursor_secret: str = "dashboard-test-cursor-secret",
    ) -> None:
        self._repository = repository
        self._target_port = target_port
        self._now = now or (lambda: datetime.now(UTC))
        self._cursor_codec = DashboardCursorCodec(cursor_secret)

    def get_overview(self, *, user_id: uuid.UUID, week_start: date | None = None) -> DashboardOverview:
        today = _local_dashboard_today(repository=self._repository, user_id=user_id, now=self._now)
        start = week_start or today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        aggregates = {
            aggregate.consumed_local_date: aggregate
            for aggregate in self._repository.get_daily_aggregates(user_id=user_id, start_date=start, end_date=end)
        }
        week = tuple(self._day_summary(day=current_day, aggregate=aggregates.get(current_day)) for current_day in _days(start, end))
        today_summary = self._day_summary(day=today, aggregate=aggregates.get(today))
        return DashboardOverview(today=today_summary, week=week, target_eligibility=self._target_port.get_dashboard_target_eligibility(user_id=user_id))

    def get_history(self, *, user_id: uuid.UUID, cursor: str | None, limit: int) -> DashboardHistoryPage:
        decoded = self._cursor_codec.decode(cursor) if cursor is not None else None
        rows = self._repository.get_history_page(user_id=user_id, cursor=decoded, limit=limit + 1)
        page_rows, has_more = rows[:limit], len(rows) > limit
        grouped: dict[date, list[DashboardHistoryRecord]] = defaultdict(list)
        for record in page_rows:
            grouped[record.consumed_local_date].append(record)
        groups = tuple(self._history_group(day=day, records=records) for day, records in grouped.items())
        next_cursor = self._cursor_codec.encode(DashboardHistoryCursor.from_record(page_rows[-1])) if has_more else None
        return DashboardHistoryPage(groups=groups, next_cursor=next_cursor)

    @staticmethod
    def _day_summary(*, day: date, aggregate: DashboardAggregate | None) -> DashboardDaySummary:
        if aggregate is None:
            return DashboardDaySummary(consumed_local_date=day, totals=DashboardNutritionTotals.empty(), meal_count=0)
        return DashboardDaySummary(consumed_local_date=day, totals=aggregate.totals, meal_count=aggregate.meal_count)

    @staticmethod
    def _history_group(*, day: date, records: list[DashboardHistoryRecord]) -> DashboardHistoryGroup:
        totals = DashboardNutritionTotals(
            energy_kcal=sum((record.energy_kcal for record in records), start=Decimal("0")),
            protein_g=sum((record.protein_g for record in records), start=Decimal("0")),
            fat_g=sum((record.fat_g for record in records), start=Decimal("0")),
            carbohydrate_g=sum((record.carbohydrate_g for record in records), start=Decimal("0")),
        )
        return DashboardHistoryGroup(
            consumed_local_date=day,
            totals=totals,
            meal_count=len(records),
            items=tuple(
                DashboardHistoryItem(
                    id=record.id,
                    consumed_at=record.consumed_at,
                    totals=DashboardNutritionTotals(
                        energy_kcal=record.energy_kcal, protein_g=record.protein_g,
                        fat_g=record.fat_g, carbohydrate_g=record.carbohydrate_g,
                    ),
                )
                for record in records
            ),
        )


class WeeklyReviewService:
    """Facts-first cache orchestration; model work begins only after deterministic coverage gates."""

    def __init__(self, *, repository: DashboardRepository, cache_repository: object, provider, public_runner: Callable[[WeeklyReviewFacts, date], object] | None = None, now: Callable[[], datetime] | None = None, graph_version: str = "weekly-review-graph-v1", prompt_version: str = "weekly-review-prompt-v1", schema_version: str = "weekly-review-schema-v1", runtime_config_version: str = "weekly-review-runtime-v1") -> None:
        self._repository, self._cache_repository, self._provider = repository, cache_repository, provider
        self._public_runner = public_runner
        self._now = now or (lambda: datetime.now(UTC))
        self._versions = (graph_version, prompt_version, schema_version, runtime_config_version)

    def get_weekly_review(self, *, user_id: uuid.UUID, week_start: date | None = None) -> WeeklyReviewResponse:
        _today, start = self._review_window(user_id=user_id, week_start=week_start)
        facts = self._facts(user_id=user_id, week_start=start)
        if facts.coverage_days < 4 or facts.meal_count < 8:
            return WeeklyReviewResponse(facts=facts, abstention_code="INSUFFICIENT_COVERAGE")
        key = WeeklyReviewCacheKey(user_id=user_id, week_start=start, facts_digest=_facts_digest(facts), graph_version=self._versions[0], prompt_version=self._versions[1], schema_version=self._versions[2], runtime_config_version=self._versions[3])
        cached = self._get_cached(key)
        if cached is not None:
            return WeeklyReviewResponse(facts=facts, cache_key=key, advice=cached)
        claimer = getattr(self._cache_repository, "claim_weekly_review", None)
        if claimer is not None:
            result, owns_claim = claimer(key=key, now=self._now())
            if not owns_claim:
                if result.status == "completed":
                    return WeeklyReviewResponse(facts=facts, cache_key=key, advice=result.advice)
                return WeeklyReviewResponse(facts=facts, cache_key=key, abstention_code="OUTCOME_UNKNOWN")
            try:
                advice = _safe_advice(self._provider(facts))
            except Exception:
                self._cache_repository.mark_weekly_review_outcome_unknown(result=result, now=self._now())
                return WeeklyReviewResponse(facts=facts, cache_key=key, abstention_code="OUTCOME_UNKNOWN")
            finalized = self._cache_repository.finalize_weekly_review(result=result, advice=advice, result_digest=_digest(advice), now=self._now())
            return WeeklyReviewResponse(facts=facts, cache_key=key, advice=finalized.advice)
        try:
            advice = _safe_advice(self._provider(facts))
        except Exception:
            return WeeklyReviewResponse(facts=facts, cache_key=key, abstention_code="OUTCOME_UNKNOWN")
        return WeeklyReviewResponse(facts=facts, cache_key=key, advice=self._save_cached(key=key, advice=advice))

    def get_public_weekly_review(
        self, *, user_id: uuid.UUID, week_start: date | None = None, refresh: bool = False
    ) -> WeeklyReviewPublicResponse:
        """Map facts and graph output to a closed user-facing enum without error leakage.

        Refresh deliberately keeps the same cache key. It can only re-attempt a transient
        service failure; it never turns insufficient coverage into a Provider request.
        """
        del refresh
        today, start = self._review_window(user_id=user_id, week_start=week_start)
        facts = self._facts(user_id=user_id, week_start=start)
        base = dict(
            week_start=start,
            week_end=start + timedelta(days=6),
            coverage_days=facts.coverage_days,
            meal_count=facts.meal_count,
            totals=facts.totals,
        )
        if facts.coverage_days < 4 or facts.meal_count < 8:
            return WeeklyReviewPublicResponse(status="insufficient_coverage", suggestions=(), **base)

        key = WeeklyReviewCacheKey(
            user_id=user_id, week_start=start, facts_digest=_facts_digest(facts),
            graph_version=self._versions[0], prompt_version=self._versions[1],
            schema_version=self._versions[2], runtime_config_version=self._versions[3],
        )
        cached = self._get_cached(key)
        if cached is not None:
            suggestions = _decode_suggestions(cached)
            if suggestions is not None:
                return WeeklyReviewPublicResponse(status="success", suggestions=suggestions, **base)

        if self._public_runner is None:
            return WeeklyReviewPublicResponse(status="retryable_error", suggestions=(), **base)
        try:
            result = self._public_runner(facts, today)
        except Exception:
            return WeeklyReviewPublicResponse(status="retryable_error", suggestions=(), **base)

        code = getattr(result, "code", "")
        suggestions = tuple(item for item in getattr(result, "suggestions", ()) if isinstance(item, str))
        if code == "COMPLETED" and 1 <= len(suggestions) <= 3:
            serialized = json.dumps(suggestions, ensure_ascii=False, separators=(",", ":"))
            saved = self._save_cached(key=key, advice=serialized)
            decoded = _decode_suggestions(saved)
            if decoded is not None:
                return WeeklyReviewPublicResponse(status="success", suggestions=decoded, **base)
        if code in {"PROVIDER_FAILURE", "WEEKLY_REVIEW_TIMEOUT"}:
            return WeeklyReviewPublicResponse(status="retryable_error", suggestions=(), **base)
        return WeeklyReviewPublicResponse(status="safety_abstain", suggestions=(), **base)

    def _facts(self, *, user_id: uuid.UUID, week_start: date) -> WeeklyReviewFacts:
        rows = self._repository.get_daily_aggregates(user_id=user_id, start_date=week_start, end_date=week_start + timedelta(days=6))
        totals = DashboardNutritionTotals(energy_kcal=sum((row.totals.energy_kcal for row in rows), start=Decimal("0")), protein_g=sum((row.totals.protein_g for row in rows), start=Decimal("0")), fat_g=sum((row.totals.fat_g for row in rows), start=Decimal("0")), carbohydrate_g=sum((row.totals.carbohydrate_g for row in rows), start=Decimal("0")))
        return WeeklyReviewFacts(week_start=week_start, coverage_days=len(rows), meal_count=sum(row.meal_count for row in rows), totals=totals, approved_patterns=tuple(f"MEALS_LOGGED_{row.consumed_local_date.isoformat()}" for row in rows if row.meal_count > 0))

    def _review_window(self, *, user_id: uuid.UUID, week_start: date | None) -> tuple[date, date]:
        today = _local_dashboard_today(repository=self._repository, user_id=user_id, now=self._now)
        current_start = today - timedelta(days=today.weekday())
        start = week_start or current_start
        if start.weekday() != 0 or start > current_start:
            raise WeeklyReviewWeekStartInvalid("weekly review must use a current or completed Monday")
        return today, start

    def _get_cached(self, key: WeeklyReviewCacheKey) -> str | None:
        getter = getattr(self._cache_repository, "get_completed", None) or getattr(self._cache_repository, "get_completed_weekly_review", None)
        if getter is None:
            return None
        value = getter(key=key)
        return value if isinstance(value, str) else (value.advice if value is not None else None)

    def _save_cached(self, *, key: WeeklyReviewCacheKey, advice: str) -> str:
        saver = getattr(self._cache_repository, "save_completed", None)
        if saver is not None:
            value = saver(key=key, advice=advice, agent_run_id=None)
            return value if isinstance(value, str) else value.advice
        value = self._cache_repository.save_completed_weekly_review(key=key, advice=advice, result_digest=_digest(advice), now=self._now(), agent_run_id=None)
        return value.advice


def _days(start: date, end: date) -> tuple[date, ...]:
    return tuple(start + timedelta(days=index) for index in range((end - start).days + 1))


def _local_dashboard_today(
    *, repository: DashboardRepository, user_id: uuid.UUID, now: Callable[[], datetime]
) -> date:
    preference = repository.get_dashboard_timezone_for_user(user_id=user_id)
    if preference is None:
        raise DashboardTimezonePreconditionError("dashboard timezone confirmation is required")
    try:
        zone = ZoneInfo(preference.time_zone)
    except (TypeError, ZoneInfoNotFoundError) as error:
        raise DashboardTimezonePreconditionError("dashboard timezone confirmation is required") from error
    instant = now()
    if instant.tzinfo is None:
        raise RuntimeError("dashboard clock must return an aware instant")
    return instant.astimezone(zone).date()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _facts_digest(facts: WeeklyReviewFacts) -> str:
    return _digest(json.dumps(facts.model_dump(mode="json"), sort_keys=True, separators=(",", ":")))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_advice(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 500:
        raise ValueError("weekly review provider response is not a safe advice string")
    return value.strip()


def _decode_suggestions(value: str) -> tuple[str, ...] | None:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(decoded, list) or not 1 <= len(decoded) <= 3 or not all(isinstance(item, str) and item.strip() for item in decoded):
        return None
    return tuple(item.strip() for item in decoded)
