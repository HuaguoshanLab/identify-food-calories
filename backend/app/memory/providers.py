"""Config-selected Memory adapters; raw conversations never enter this boundary."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.config import ConfigurationError, Settings
from app.memory.ports import MemoryProvider, MemoryReplicaMissing, MemorySearchHit


@dataclass(frozen=True, slots=True)
class FakeMemoryProviderCall:
    operation: str
    user_id: uuid.UUID
    external_id: str | None
    request_key: str | None = None
    infer: bool | None = None


class FakeMemoryProvider:
    """Deterministic, network-free provider used by tests and local development."""

    def __init__(self) -> None:
        self._memories: dict[str, tuple[uuid.UUID, str, str]] = {}
        self._direct_records: dict[str, tuple[uuid.UUID, str, str, bool]] = {}
        self.calls: list[FakeMemoryProviderCall] = []
        self.fail_next_delete = False

    def create(self, *, user_id: uuid.UUID, category: str, canonical_text: str) -> str:
        # IDs may be persisted beyond this fake instance or process lifetime.
        external_id = f"fake-memory-{uuid.uuid4()}"
        self._memories[external_id] = (user_id, category, canonical_text)
        self.calls.append(FakeMemoryProviderCall("create", user_id, external_id))
        return external_id

    @property
    def direct_records(self) -> dict[str, tuple[uuid.UUID, str, str, bool]]:
        return dict(self._direct_records)

    def resolve_direct_by_request_key(
        self, *, user_id: uuid.UUID, request_key: str
    ) -> str | None:
        self.calls.append(FakeMemoryProviderCall("resolve_direct", user_id, None, request_key))
        record = self._direct_records.get(request_key)
        if record is None:
            return None
        if record[0] != user_id:
            raise LookupError("memory is unavailable")
        return f"fake-direct-{request_key}"

    def create_direct(
        self,
        *,
        user_id: uuid.UUID,
        category: str,
        canonical_text: str,
        request_key: str,
    ) -> str:
        existing = self._direct_records.get(request_key)
        if existing is not None:
            if existing[0] != user_id:
                raise LookupError("memory is unavailable")
            return f"fake-direct-{request_key}"
        self._direct_records[request_key] = (user_id, category, canonical_text, False)
        external_id = f"fake-direct-{request_key}"
        self._memories[external_id] = (user_id, category, canonical_text)
        self.calls.append(
            FakeMemoryProviderCall("create_direct", user_id, external_id, request_key, False)
        )
        return external_id

    def update(self, *, user_id: uuid.UUID, external_id: str, category: str, canonical_text: str) -> None:
        owner = self._memories.get(external_id)
        if owner is None:
            raise MemoryReplicaMissing("memory replica is unavailable")
        if owner[0] != user_id:
            raise LookupError("memory is unavailable")
        self._memories[external_id] = (user_id, category, canonical_text)
        self.calls.append(FakeMemoryProviderCall("update", user_id, external_id))

    def delete(self, *, user_id: uuid.UUID, external_id: str) -> None:
        self.calls.append(FakeMemoryProviderCall("delete", user_id, external_id))
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise TimeoutError("scripted transient provider failure")
        owner = self._memories.get(external_id)
        if owner is not None and owner[0] != user_id:
            raise LookupError("memory is unavailable")
        self._memories.pop(external_id, None)
        self._direct_records = {
            request_key: record
            for request_key, record in self._direct_records.items()
            if f"fake-direct-{request_key}" != external_id
        }

    def search(self, *, user_id: uuid.UUID, query: str, limit: int) -> list[MemorySearchHit]:
        normalized = query.casefold()
        self.calls.append(FakeMemoryProviderCall("search", user_id, None))
        return [MemorySearchHit(external_id=external_id, canonical_text=text) for external_id, (owner, _category, text) in self._memories.items() if owner == user_id and normalized in text.casefold()][:limit]


class Mem0MemoryProvider:
    """Thin SDK adapter. Application-local ledger authorization always happens before this code."""

    def __init__(self, *, api_key: str, endpoint: str) -> None:
        from mem0 import MemoryClient

        self._client = MemoryClient(api_key=api_key, host=endpoint)

    def create(self, *, user_id: uuid.UUID, category: str, canonical_text: str) -> str:
        result = self._client.add(
            messages=[{"role": "user", "content": canonical_text}],
            user_id=str(user_id),
            metadata={"category": category, "source": "food-agent"},
            infer=False,
        )
        entries = self._result_entries(result)
        ids = [entry["id"] for entry in entries if isinstance(entry.get("id"), str)]
        if len(ids) != 1:
            raise RuntimeError("Mem0 create must return exactly one id")
        return ids[0]

    def resolve_direct_by_request_key(
        self, *, user_id: uuid.UUID, request_key: str
    ) -> str | None:
        result = self._client.get_all(
            filters={"user_id": str(user_id), "metadata": {"request_key": request_key}},
            page_size=2,
        )
        entries = self._result_entries(result)
        matches = [
            entry
            for entry in entries
            if isinstance(entry.get("metadata"), dict)
            and entry["metadata"].get("request_key") == request_key
        ]
        if not matches:
            return None
        if len(matches) != 1 or not isinstance(matches[0].get("id"), str):
            raise RuntimeError("Mem0 direct request-key resolve must return exactly one id")
        return matches[0]["id"]

    def create_direct(
        self,
        *,
        user_id: uuid.UUID,
        category: str,
        canonical_text: str,
        request_key: str,
    ) -> str:
        result = self._client.add(
            messages=[{"role": "user", "content": canonical_text}],
            user_id=str(user_id),
            metadata={
                "category": category,
                "source": "food-agent-direct.v1",
                "request_key": request_key,
            },
            infer=False,
        )
        entries = self._result_entries(result)
        ids = [entry["id"] for entry in entries if isinstance(entry.get("id"), str)]
        if len(ids) != 1:
            raise RuntimeError("Mem0 direct create must return exactly one id")
        return ids[0]

    def update(self, *, user_id: uuid.UUID, external_id: str, category: str, canonical_text: str) -> None:
        # Preserve the immutable request key used to resolve uncertain writes.
        # Category and ownership cannot be changed by the local edit endpoint.
        del user_id, category
        self._client.update(external_id, text=canonical_text)

    def delete(self, *, user_id: uuid.UUID, external_id: str) -> None:
        del user_id  # The ledger checked it before this opaque external ID reaches the adapter.
        self._client.delete(external_id)

    def search(self, *, user_id: uuid.UUID, query: str, limit: int) -> list[MemorySearchHit]:
        result = self._client.search(query, filters={"user_id": str(user_id)}, top_k=limit)
        entries = result.get("results", result) if isinstance(result, dict) else result
        return [MemorySearchHit(external_id=str(entry["id"]), canonical_text=str(entry.get("memory", ""))) for entry in entries if isinstance(entry, dict) and entry.get("id") and entry.get("memory")]

    @staticmethod
    def _result_entries(result: object) -> list[dict[str, object]]:
        if not isinstance(result, dict):
            return []
        raw_entries = result.get("results") or result.get("memories")
        if raw_entries is None and result.get("id"):
            raw_entries = [result]
        if not isinstance(raw_entries, list):
            return []
        return [entry for entry in raw_entries if isinstance(entry, dict)]


def create_memory_provider(settings: Settings) -> MemoryProvider:
    if settings.app_env == "test" or settings.memory_provider_mode == "fake":
        return FakeMemoryProvider()
    if settings.memory_provider_mode != "mem0":
        raise ConfigurationError("unsupported memory provider mode")
    if settings.mem0_api_key is None or not settings.mem0_api_key.get_secret_value() or not settings.mem0_endpoint:
        raise ConfigurationError("MEM0_API_KEY and MEM0_ENDPOINT are required for the Mem0 provider")
    return Mem0MemoryProvider(api_key=settings.mem0_api_key.get_secret_value(), endpoint=settings.mem0_endpoint)
