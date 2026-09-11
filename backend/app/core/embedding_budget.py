"""Cross-process, fail-closed monthly budget reservation for embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Callable

from sqlalchemy import Engine, create_engine, text


class EmbeddingBudgetUnavailable(RuntimeError):
    """Accounting cannot safely reserve a provider call."""


LEDGER_AMOUNT_SCALE = 8
LEDGER_AMOUNT_QUANTUM = Decimal("0.00000001")
LEDGER_MAX_AMOUNT_CNY = Decimal("9999999999.99999999")


def require_ledger_amount(value: Decimal, *, variable: str) -> Decimal:
    """Reject values PostgreSQL ``NUMERIC(18, 8)`` would silently round or overflow.

    A cost cap is a security boundary.  Letting PostgreSQL round a sub-precision
    cap to zero turns an approved reservation into an unbounded sequence of
    no-op reservations, so callers must supply an exactly representable positive
    amount before a transaction starts.
    """

    try:
        if not value.is_finite() or value <= 0:
            raise ValueError(f"{variable} must be a finite positive amount")
        if value.as_tuple().exponent < -LEDGER_AMOUNT_SCALE:
            raise ValueError(
                f"{variable} must have at most {LEDGER_AMOUNT_SCALE} decimal places"
            )
        if value > LEDGER_MAX_AMOUNT_CNY:
            raise ValueError(
                f"{variable} must not exceed {LEDGER_MAX_AMOUNT_CNY}"
            )
    except (InvalidOperation, ValueError) as error:
        if isinstance(error, ValueError):
            raise
        raise ValueError(f"{variable} must be a finite positive amount") from error
    return value


def round_cost_up_for_ledger(value: Decimal) -> Decimal:
    """Round a computed vendor charge upward so accounting never undercounts it."""

    try:
        if not value.is_finite() or value < 0:
            raise ValueError("computed embedding cost must be finite and non-negative")
        rounded = value.quantize(LEDGER_AMOUNT_QUANTUM, rounding=ROUND_CEILING)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("computed embedding cost is incompatible with the budget ledger") from error
    if rounded > LEDGER_MAX_AMOUNT_CNY:
        raise ValueError("computed embedding cost exceeds the budget ledger range")
    return rounded


@dataclass(frozen=True)
class EmbeddingBudgetReservation:
    period_key: str
    amount_cny: Decimal


class PostgresEmbeddingBudgetLedger:
    """Reserve before a vendor request so concurrent workers share one hard cap."""

    def __init__(self, *, database_url: str, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._engine: Engine = create_engine(database_url, pool_pre_ping=True)
        self._now = now

    def reserve(self, *, amount_cny: Decimal, cap_cny: Decimal) -> EmbeddingBudgetReservation | None:
        try:
            require_ledger_amount(amount_cny, variable="embedding reservation amount")
            require_ledger_amount(cap_cny, variable="embedding period cap")
        except ValueError as error:
            raise EmbeddingBudgetUnavailable("embedding budget reservation is invalid") from error
        period_key = self._now().astimezone(UTC).strftime("%Y-%m")
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO embedding_provider_period_budgets "
                        "(period_key, reserved_cny, spent_cny, updated_at) "
                        "VALUES (:period_key, 0, 0, CURRENT_TIMESTAMP) "
                        "ON CONFLICT (period_key) DO NOTHING"
                    ),
                    {"period_key": period_key},
                )
                accepted = connection.execute(
                    text(
                        "UPDATE embedding_provider_period_budgets "
                        "SET reserved_cny = reserved_cny + :amount, updated_at = CURRENT_TIMESTAMP "
                        "WHERE period_key = :period_key "
                        "AND spent_cny + reserved_cny + :amount <= :cap "
                        "RETURNING period_key"
                    ),
                    {"period_key": period_key, "amount": amount_cny, "cap": cap_cny},
                ).scalar_one_or_none()
        except Exception as error:  # Database outage must not unlock paid calls.
            raise EmbeddingBudgetUnavailable("embedding budget ledger is unavailable") from error
        return EmbeddingBudgetReservation(period_key=period_key, amount_cny=amount_cny) if accepted else None

    def settle(self, reservation: EmbeddingBudgetReservation, *, actual_cost_cny: Decimal) -> None:
        # A failed settlement deliberately leaves the reservation held, which is
        # conservative when a provider request may have consumed paid tokens.
        try:
            actual_cost_cny = round_cost_up_for_ledger(actual_cost_cny)
            require_ledger_amount(reservation.amount_cny, variable="embedding reservation amount")
        except ValueError as error:
            raise EmbeddingBudgetUnavailable("embedding budget settlement is invalid") from error
        if actual_cost_cny > reservation.amount_cny:
            raise EmbeddingBudgetUnavailable("embedding budget settlement is invalid")
        try:
            with self._engine.begin() as connection:
                changed = connection.execute(
                    text(
                        "UPDATE embedding_provider_period_budgets "
                        "SET reserved_cny = reserved_cny - :reserved, "
                        "spent_cny = spent_cny + :actual, updated_at = CURRENT_TIMESTAMP "
                        "WHERE period_key = :period_key AND reserved_cny >= :reserved"
                    ),
                    {
                        "period_key": reservation.period_key,
                        "reserved": reservation.amount_cny,
                        "actual": actual_cost_cny,
                    },
                ).rowcount
        except Exception as error:
            raise EmbeddingBudgetUnavailable("embedding budget settlement is unavailable") from error
        if changed != 1:
            raise EmbeddingBudgetUnavailable("embedding budget reservation was lost")
