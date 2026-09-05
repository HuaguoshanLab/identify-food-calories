"""CSV exchange behavior: bounded validation, safe export, atomic idempotent import."""

import csv
import io
import uuid

import pytest

from app.admin.catalog_csv import CatalogCsvInvalid, parse_catalog_csv, write_catalog_csv
from app.admin.schemas import CatalogCsvImportCommand, CatalogDraftResponse, CatalogListQuery
from app.admin.service import AdminPermissionDenied, AdminService, CatalogDraftConflict
from app.auth.models import UserRole
from tests.admin.test_catalog_draft_service import FakeCatalogDraftRepository, NOW, _admin, _create


def csv_content(*names: str) -> str:
    return write_catalog_csv([CatalogDraftResponse(**_create().model_dump(mode="json", exclude={"reason"}) | {
        "id": uuid.uuid4(), "revision": 1, "canonical_name": name,
    }) for name in names]).decode("utf-8-sig")


class CsvRepository(FakeCatalogDraftRepository):
    def acquire_catalog_import_lock(self, command_key: str) -> None:
        self.lock = command_key

    def list_catalog_drafts(self, *, query, limit, offset):
        self.query = query
        drafts = list(self.drafts.values())
        return drafts[offset:offset + limit], len(drafts)


def test_csv_round_trip_quotes_unicode_numeric_precision_and_bom():
    text = csv_content('燕麦,"片"', '多行\n名称')
    preview = parse_catalog_csv('\ufeff' + text)
    assert not preview.errors
    assert preview.total_rows == 2
    assert [row.canonical_name for row in preview.rows] == ['燕麦,"片"', '多行\n名称']
    assert str(preview.rows[0].protein_g_per_100g) == '16.9'


def test_csv_errors_report_line_and_field_without_echoing_unsafe_values():
    text = csv_content('Oats').replace('389,', '-99,').replace('https://fdc.nal.usda.gov/', 'http://bad.example/')
    preview = parse_catalog_csv(text)
    assert preview.valid_rows == 0
    assert [(error.row, error.field) for error in preview.errors] == [(2, '能量(kcal/100g)'), (2, '来源链接')]
    assert 'bad.example' not in preview.model_dump_json()
    duplicate = parse_catalog_csv(csv_content('Oats', 'OATS'))
    assert duplicate.errors[0].row == 3
    assert duplicate.valid_rows == 1


@pytest.mark.parametrize('content', ['', 'wrong,header\na,b', 'a\x00b', csv_content(*[str(i) for i in range(501)]), 'x' * 1_048_577])
def test_csv_rejects_invalid_headers_empty_oversize_and_too_many_rows(content):
    with pytest.raises(CatalogCsvInvalid):
        parse_catalog_csv(content)


def test_export_neutralizes_spreadsheet_formulas_in_all_text_fields():
    record = CatalogDraftResponse(**_create().model_dump(mode='json', exclude={'reason'}) | {
        'id': uuid.uuid4(), 'revision': 1, 'canonical_name': ' =1+2', 'aliases': ['@SUM(1)'], 'source_name': '+cmd',
    })
    output = write_catalog_csv([record])
    assert output.startswith(b'\xef\xbb\xbf')
    row = list(csv.reader(io.StringIO(output.decode('utf-8-sig'))))[1]
    assert row[0] == "' =1+2" and row[1] == "'@SUM(1)" and row[6] == "'+cmd"


def test_import_commits_once_audits_each_row_and_replays_without_duplicates():
    actor = _admin()
    repo = CsvRepository(actor)
    commits = []
    service = AdminService(repository=repo, now=lambda: NOW, commit=lambda: commits.append(True))
    command = CatalogCsvImportCommand(csv_text=csv_content('燕麦', '米饭'), reason='核对来源后批量建档', confirm=True)
    result = service.import_catalog_csv(actor_user_id=actor.id, command=command, command_key='import-test-00001')
    assert result.imported_count == 2 and len(commits) == 1
    assert len(repo.events) == len(repo.revisions) == len(repo.drafts) == 2
    assert all(event.reason == command.reason for event in repo.events)
    replay = service.import_catalog_csv(actor_user_id=actor.id, command=command, command_key='import-test-00001')
    assert replay == result
    assert len(repo.drafts) == len(repo.events) == 2
    with pytest.raises(CatalogDraftConflict):
        service.import_catalog_csv(actor_user_id=actor.id, command=command.model_copy(update={'reason': 'changed reason'}), command_key='import-test-00001')
    page = service.list_catalog_drafts(actor_user_id=actor.id, query=CatalogListQuery(page_size=1, page=2))
    assert page.total == 2 and len(page.items) == 1 and page.items[0].canonical_name == '米饭'


def test_invalid_row_blocks_entire_import_and_persistence_failure_rolls_back():
    actor = _admin()
    repo = CsvRepository(actor)
    rollbacks = []
    commits = []
    service = AdminService(repository=repo, now=lambda: NOW, commit=lambda: commits.append(True), rollback=lambda: rollbacks.append(True))
    command = CatalogCsvImportCommand(csv_text=csv_content('Oats', 'Oats'), reason='test import', confirm=True)
    with pytest.raises(CatalogCsvInvalid):
        service.import_catalog_csv(actor_user_id=actor.id, command=command, command_key='import-test-00002')
    assert not repo.drafts and not repo.events and not commits
    def fail(_draft):
        raise RuntimeError('persistence unavailable')
    repo.add_catalog_draft = fail
    with pytest.raises(RuntimeError):
        service.import_catalog_csv(actor_user_id=actor.id, command=command.model_copy(update={'csv_text': csv_content('Oats')}), command_key='import-test-00002')
    assert rollbacks == [True] and not commits


def test_csv_and_list_capabilities_always_reload_database_role():
    user = _admin(UserRole.USER.value)
    service = AdminService(repository=CsvRepository(user))
    calls = [lambda: service.list_catalog_drafts(actor_user_id=user.id, query=CatalogListQuery()),
        lambda: service.export_catalog_csv(actor_user_id=user.id, query=CatalogListQuery()),
        lambda: service.catalog_csv_template(actor_user_id=user.id),
        lambda: service.preview_catalog_csv(actor_user_id=user.id, csv_text='invalid'),
        lambda: service.import_catalog_csv(actor_user_id=user.id, command=CatalogCsvImportCommand(csv_text='invalid', reason='test', confirm=True), command_key='test-key-00000001')]
    for call in calls:
        with pytest.raises(AdminPermissionDenied):
            call()
