"""Bounded UTF-8 CSV parsing for managed recipe candidates."""

import csv
import io
from collections.abc import Sequence

from pydantic import ValidationError

from app.admin.catalog_csv import MAX_CSV_BYTES, MAX_IMPORT_ROWS, _safe_cell
from app.admin.schemas import (
    RecipeCandidateCsvError,
    RecipeCandidateCsvPreview,
    RecipeCandidateCsvRow,
    RecipeCandidateResponse,
)

RECIPE_CSV_COLUMNS = {
    "关联目录菜品名称": "catalog_food_name",
    "餐次": "meal_slot",
    "单份克数": "portion_grams",
    "份量说明": "portion_description",
    "做法标签": "method_tags",
    "口味标签": "flavour_tags",
    "状态": "status",
    "餐内角色": "meal_role",
}
LEGACY_RECIPE_CSV_COLUMNS = {label: field for label, field in RECIPE_CSV_COLUMNS.items() if field != "meal_role"}
ROLE_LABELS = {"standalone": "单独候选", "staple": "主食", "protein": "蛋白质菜", "vegetable": "蔬菜", "side": "其他配菜", "drink": "饮品"}
MEAL_LABELS = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}
STATUS_LABELS = {"pending": "待审核", "enabled": "已启用", "disabled": "已停用"}


class RecipeCandidateCsvInvalid(ValueError):
    pass


def parse_recipe_candidate_csv(content: str) -> RecipeCandidateCsvPreview:
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise RecipeCandidateCsvInvalid("文件不能超过 1 MB。")
    if "\x00" in content or "\ufffd" in content:
        raise RecipeCandidateCsvInvalid("请使用 UTF-8 编码的 CSV 文件。")
    try:
        reader = csv.reader(
            io.StringIO(content.lstrip("\ufeff"), newline=""), strict=True
        )
        header = next(reader, None)
        columns = LEGACY_RECIPE_CSV_COLUMNS if header == list(LEGACY_RECIPE_CSV_COLUMNS) else RECIPE_CSV_COLUMNS
        if header != list(columns):
            raise RecipeCandidateCsvInvalid(
                "表头不匹配，请下载并使用导入模板，保留列名与顺序。"
            )
        rows: list[RecipeCandidateCsvRow] = []
        errors: list[RecipeCandidateCsvError] = []
        seen: set[tuple[str, str]] = set()
        count = 0
        for record in reader:
            if not record or all(not cell.strip() for cell in record):
                continue
            count += 1
            if count > MAX_IMPORT_ROWS:
                raise RecipeCandidateCsvInvalid("每次最多导入 500 条，请拆分文件。")
            if len(record) != len(columns):
                errors.append(
                    RecipeCandidateCsvError(
                        row=reader.line_num, field="整行", message="列数与模板不一致。"
                    )
                )
                continue
            raw = dict(zip(columns.values(), record, strict=True))
            raw["method_tags"] = tuple(
                value.strip() for value in str(raw["method_tags"]).split("|")
            )
            raw["flavour_tags"] = tuple(
                value.strip() for value in str(raw["flavour_tags"]).split("|")
            )
            raw["meal_slot"] = {label: key for key, label in MEAL_LABELS.items()}.get(
                str(raw["meal_slot"]).strip(), raw["meal_slot"]
            )
            raw["status"] = {label: key for key, label in STATUS_LABELS.items()}.get(
                str(raw["status"]).strip(), raw["status"]
            )
            if "meal_role" in raw:
                role = str(raw["meal_role"]).strip()
                raw["meal_role"] = {label: key for key, label in ROLE_LABELS.items()}.get(role, role)
            try:
                candidate = RecipeCandidateCsvRow.model_validate(raw)
            except ValidationError as error:
                labels = {value: key for key, value in RECIPE_CSV_COLUMNS.items()}
                for issue in error.errors(include_input=False, include_url=False):
                    errors.append(
                        RecipeCandidateCsvError(
                            row=reader.line_num,
                            field=labels.get(str(issue["loc"][0]), "整行"),
                            message="字段缺失或格式不正确，请核对模板。",
                        )
                    )
                continue
            key = (candidate.catalog_food_name.casefold(), candidate.meal_slot)
            if key in seen:
                errors.append(
                    RecipeCandidateCsvError(
                        row=reader.line_num,
                        field="关联目录菜品名称",
                        message="同一目录菜品和餐次不能重复。",
                    )
                )
                continue
            seen.add(key)
            rows.append(candidate)
    except csv.Error as error:
        raise RecipeCandidateCsvInvalid("CSV 格式无效，请检查引号和分隔符。") from error
    if not count:
        raise RecipeCandidateCsvInvalid("文件中没有数据，请在表头下填写菜品。")
    return RecipeCandidateCsvPreview(
        total_rows=count, valid_rows=len(rows), rows=rows, errors=errors
    )


def write_recipe_candidate_csv(
    rows: Sequence[RecipeCandidateCsvRow | RecipeCandidateResponse],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(RECIPE_CSV_COLUMNS)
    for row in rows:
        values = row.model_dump() | {
            "method_tags": "|".join(row.method_tags),
            "flavour_tags": "|".join(row.flavour_tags),
            "meal_slot": MEAL_LABELS[str(row.meal_slot)],
            "status": STATUS_LABELS[str(row.status)],
            "meal_role": ROLE_LABELS[row.meal_role],
        }
        writer.writerow(
            [_safe_cell(values[field]) for field in RECIPE_CSV_COLUMNS.values()]
        )
    return output.getvalue().encode("utf-8-sig")
