"""Bounded CSV exchange for catalog drafts; no database or HTTP dependencies."""

import csv
import io
from collections.abc import Sequence

from pydantic import ValidationError

from app.admin.schemas import CatalogCsvError, CatalogCsvPreview, CatalogDraftCreateCommand, CatalogDraftResponse

MAX_CSV_BYTES = 1_048_576
MAX_IMPORT_ROWS = 500
MAX_EXPORT_ROWS = 10_000
CSV_COLUMNS = {
    "菜品名称": "canonical_name", "别名": "aliases", "能量(kcal/100g)": "energy_kcal_per_100g",
    "蛋白质(g/100g)": "protein_g_per_100g", "脂肪(g/100g)": "fat_g_per_100g",
    "碳水(g/100g)": "carbohydrate_g_per_100g", "来源名称": "source_name",
    "来源链接": "source_url", "授权状态": "authorization_status",
}
STATUS_LABELS = {"pending": "待确认", "authorized": "已授权", "revoked": "已撤销"}


class CatalogCsvInvalid(ValueError):
    """Safe file-level validation failure, never includes file contents."""


def parse_catalog_csv(content: str) -> CatalogCsvPreview:
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise CatalogCsvInvalid("文件不能超过 1 MB。")
    if "\x00" in content or "\ufffd" in content:
        raise CatalogCsvInvalid("请使用 UTF-8 编码的 CSV 文件。")
    reader = csv.reader(io.StringIO(content.lstrip("\ufeff"), newline=""), strict=True)
    errors: list[CatalogCsvError] = []
    rows: list[CatalogDraftCreateCommand] = []
    seen: set[str] = set()
    count = 0
    try:
        header = next(reader, None)
        if header != list(CSV_COLUMNS):
            raise CatalogCsvInvalid("表头不匹配，请下载并使用导入模板，保留列名与顺序。")
        for record in reader:
            if not record or all(not cell.strip() for cell in record):
                continue
            count += 1
            if count > MAX_IMPORT_ROWS:
                raise CatalogCsvInvalid("每次最多导入 500 条，请拆分文件。")
            line = reader.line_num
            if len(record) != len(header):
                errors.append(CatalogCsvError(row=line, field="整行", message="列数与模板不一致。"))
                continue
            values = dict(zip(CSV_COLUMNS.values(), record, strict=True))
            values["aliases"] = [alias.strip() for alias in str(values["aliases"]).split("|")]
            status = str(values["authorization_status"]).strip()
            values["authorization_status"] = {v: k for k, v in STATUS_LABELS.items()}.get(status, status)
            try:
                candidate = CatalogDraftCreateCommand.model_validate(values | {"reason": "CSV preview"})
            except ValidationError as error:
                field_labels = {value: key for key, value in CSV_COLUMNS.items()}
                for issue in error.errors(include_input=False, include_url=False):
                    errors.append(CatalogCsvError(row=line, field=field_labels.get(str(issue["loc"][0]), "整行"),
                        message="字段缺失或格式不正确，请核对模板、数值范围及 HTTPS 来源链接。"))
                continue
            name = candidate.canonical_name.casefold()
            if name in seen:
                errors.append(CatalogCsvError(row=line, field="菜品名称", message="文件内菜品名称重复，请合并或修改名称。"))
                continue
            seen.add(name)
            rows.append(candidate)
    except csv.Error as error:
        raise CatalogCsvInvalid("CSV 格式无效，请检查引号和分隔符。") from error
    if not count:
        raise CatalogCsvInvalid("文件中没有数据，请在表头下填写目录内容。")
    return CatalogCsvPreview(total_rows=count, valid_rows=len(rows), rows=rows, errors=errors)


def _safe_cell(value: object) -> str:
    cell = str(value)
    # Quoting alone does not stop Excel formula execution on downloaded CSV.
    if cell.lstrip().startswith(("=", "+", "-", "@")) or cell.startswith(("\t", "\r", "\n")):
        return "'" + cell
    return cell


def write_catalog_csv(drafts: Sequence[CatalogDraftResponse]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for draft in drafts:
        values = draft.model_dump()
        values["aliases"] = "|".join(draft.aliases)
        values["authorization_status"] = STATUS_LABELS[draft.authorization_status]
        writer.writerow([_safe_cell(values[key]) for key in CSV_COLUMNS.values()])
    return output.getvalue().encode("utf-8-sig")
