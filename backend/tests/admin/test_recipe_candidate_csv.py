"""CSV contracts for administrator-managed prepared-dish candidates."""

from __future__ import annotations

import csv
import io
import uuid

import pytest
from pydantic import ValidationError

from app.admin.recipe_csv import (
    RecipeCandidateCsvInvalid,
    parse_recipe_candidate_csv,
    write_recipe_candidate_csv,
)
from app.admin.schemas import (
    RecipeCandidateBulkCommand,
    RecipeCandidateCsvRow,
    RecipeCandidateResponse,
)


def row(*, name: str = "辣椒炒肉", slot: str = "lunch") -> RecipeCandidateCsvRow:
    return RecipeCandidateCsvRow(
        catalog_food_name=name,
        meal_slot=slot,
        portion_grams="200",
        portion_description="一份",
        method_tags=("炒",),
        flavour_tags=("微辣",),
        status="pending",
    )


def csv_text(*rows: RecipeCandidateCsvRow) -> str:
    return write_recipe_candidate_csv(rows).decode("utf-8-sig")


def test_recipe_candidate_bulk_command_supports_full_current_catalog_selection() -> None:
    command = RecipeCandidateBulkCommand(
        ids=[uuid.uuid4() for _ in range(612)], reason="全选当前菜谱候选", confirm=True
    )

    assert len(command.ids) == 612
    with pytest.raises(ValidationError):
        RecipeCandidateBulkCommand(
            ids=[uuid.uuid4() for _ in range(1001)], reason="超出上限", confirm=True
        )


def test_recipe_candidate_csv_is_chinese_utf8_and_reports_row_errors_without_persisting() -> (
    None
):
    preview = parse_recipe_candidate_csv(
        csv_text(row(), row(name="清炒时蔬", slot="dinner"))
    )

    assert preview.total_rows == 2
    assert preview.valid_rows == 2
    duplicate = parse_recipe_candidate_csv(csv_text(row(), row()))
    assert duplicate.valid_rows == 1
    assert duplicate.errors[0].field == "关联目录菜品名称"
    invalid = parse_recipe_candidate_csv(csv_text(row()).replace("午餐", "宵夜"))
    assert invalid.errors[0].field == "餐次"


def test_recipe_candidate_export_neutralizes_formulas_and_template_columns_are_stable() -> (
    None
):
    output = write_recipe_candidate_csv(
        [
            RecipeCandidateResponse(
                id=uuid.uuid4(),
                catalog_food_name="=1+1",
                meal_slot="breakfast",
                portion_grams="100",
                portion_description="一份",
                method_tags=("炒",),
                flavour_tags=("家常",),
                status="enabled",
                revision=1,
            )
        ]
    )
    assert output.startswith(b"\xef\xbb\xbf")
    values = list(csv.reader(io.StringIO(output.decode("utf-8-sig"))))
    assert values[0] == [
        "关联目录菜品名称",
        "餐次",
        "单份克数",
        "份量说明",
        "做法标签",
        "口味标签",
        "状态",
    ]
    assert values[1][0] == "'=1+1"


@pytest.mark.parametrize("content", ["", "错误表头\n", "x" * 1_048_577])
def test_recipe_candidate_csv_rejects_invalid_file(content: str) -> None:
    with pytest.raises(RecipeCandidateCsvInvalid):
        parse_recipe_candidate_csv(content)
