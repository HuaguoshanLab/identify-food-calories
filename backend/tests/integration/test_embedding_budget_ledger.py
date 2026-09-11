"""Real PostgreSQL regression tests for embedding ledger monetary precision."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.embedding_budget import (
    EmbeddingBudgetUnavailable,
    PostgresEmbeddingBudgetLedger,
)


def test_ledger_never_approves_sub_precision_reservations_that_postgres_would_round_to_zero(
    test_engine,
) -> None:
    """A NUMERIC(18, 8) rounding no-op must not become an unlimited paid-call bypass."""

    period = "2026-09"
    ledger = PostgresEmbeddingBudgetLedger(
        database_url=test_engine.url.render_as_string(hide_password=False),
        now=lambda: datetime(2026, 9, 1, tzinfo=UTC),
    )
    with test_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM embedding_provider_period_budgets WHERE period_key = :period"),
            {"period": period},
        )

    # Before the precision gate, each call would UPDATE by 0.000000001; PG
    # stores that as zero and repeatedly returns an approved reservation.
    for _ in range(3):
        with pytest.raises(EmbeddingBudgetUnavailable, match="reservation is invalid"):
            ledger.reserve(
                amount_cny=Decimal("0.000000001"),
                cap_cny=Decimal("0.00000001"),
            )

    with test_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT reserved_cny, spent_cny "
                "FROM embedding_provider_period_budgets WHERE period_key = :period"
            ),
            {"period": period},
        ).one_or_none()
    assert row is None


def test_ledger_allows_one_exact_minimum_reservation_but_not_a_second(test_engine) -> None:
    ledger = PostgresEmbeddingBudgetLedger(
        database_url=test_engine.url.render_as_string(hide_password=False),
        now=lambda: datetime(2026, 9, 1, tzinfo=UTC),
    )
    amount = Decimal("0.00000001")
    with test_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM embedding_provider_period_budgets WHERE period_key = :period"),
            {"period": "2026-09"},
        )
    first = ledger.reserve(amount_cny=amount, cap_cny=amount)
    second = ledger.reserve(amount_cny=amount, cap_cny=amount)

    assert first is not None
    assert second is None
