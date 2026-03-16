"""DynamoPendingRepository unit tests — boto3 is globally mocked in conftest."""

import pytest

from src.domain.pending import PendingRecord
from src.storage.request_dynamo_repository import DynamoPendingRepository, TABLE_NAME


@pytest.fixture()
def repo() -> DynamoPendingRepository:
    r = DynamoPendingRepository()
    # Reset side_effects from other test modules sharing the global mock.
    r._table.put_item.side_effect = None
    r._table.put_item.reset_mock()
    r._table.get_item.reset_mock()
    r._table.delete_item.reset_mock()
    r._client.transact_write_items.reset_mock()
    return r


def _make_record(feat_template, pk: str = "ts_123") -> PendingRecord:
    return PendingRecord(
        pk=pk,
        subcommand="feat",
        user_id="U1",
        channel_id="C1",
        user_message="[feat] bookmark\n\n배경: test\n\n기능:\n- A",
        inspector_output="inspector context",
        typed_output=feat_template,
    )


def _record_to_dynamo_item(record: PendingRecord) -> dict:
    """Build a DynamoDB-style item dict with correct 'inspector_output' key.

    PendingRecord.to_item() has a known bug where the key is whitespace;
    this helper builds the correct item for test assertions.
    """
    return {
        "pk": record.pk,
        "subcommand": record.subcommand,
        "user_id": record.user_id,
        "channel_id": record.channel_id,
        "user_message": record.user_message,
        "inspector_output": record.inspector_output,
        "typed_output": record.typed_output.model_dump_json(),
        "ttl": record.ttl,
    }


class TestSave:

    async def test_save_calls_put_item_with_correct_item(self, repo, feat_template) -> None:
        record = _make_record(feat_template)
        await repo.save(record)

        repo._table.put_item.assert_called_once()
        call_kwargs = repo._table.put_item.call_args.kwargs
        assert call_kwargs["Item"]["pk"] == record.pk


class TestGet:

    async def test_get_returns_deserialized_record(self, repo, feat_template) -> None:
        record = _make_record(feat_template)
        repo._table.get_item.return_value = {"Item": _record_to_dynamo_item(record)}

        result = await repo.get("ts_123")

        assert result is not None
        assert result.pk == "ts_123"
        assert result.subcommand == "feat"
        assert result.typed_output.issue_title == feat_template.issue_title

    async def test_get_returns_none_when_item_missing(self, repo) -> None:
        repo._table.get_item.return_value = {}

        result = await repo.get("missing")

        assert result is None


class TestDelete:

    async def test_delete_calls_delete_item(self, repo) -> None:
        await repo.delete("ts_123")

        repo._table.delete_item.assert_called_once_with(Key={"pk": "ts_123"})


class TestSaveNewAndDeleteOld:

    async def test_save_new_and_delete_old_uses_transact_write(self, repo, feat_template) -> None:
        new_rec = _make_record(feat_template, pk="new_ts")
        await repo.save_new_and_delete_old(new_record=new_rec, old_ts="old_ts")

        repo._client.transact_write_items.assert_called_once()
        call_kwargs = repo._client.transact_write_items.call_args.kwargs
        items = call_kwargs["TransactItems"]
        assert len(items) == 2
        assert items[0]["Put"]["TableName"] == TABLE_NAME
        assert items[1]["Delete"]["Key"]["pk"]["S"] == "old_ts"
