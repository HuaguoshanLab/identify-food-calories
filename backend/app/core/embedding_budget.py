"""Cross-process, fail-closed monthly budget reservation for embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Callable

from sqlalchemy import Engine, create_engine, text


class EmbeddingBudgetUnavailable(RuntimeError):
    """Accounting cannot safely reserve a provider call."""


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
        if actual_cost_cny < 0 or actual_cost_cny > reservation.amount_cny:
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
