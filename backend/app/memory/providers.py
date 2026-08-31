"""Config-selected Memory adapters; raw conversations never enter this boundary."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.config import ConfigurationError, Settings
from app.memory.ports import MemoryProvider, MemorySearchHit


@dataclass(frozen=True, slots=True)
class FakeMemoryProviderCall:
    operation: str
    user_id: uuid.UUID
    external_id: str | None


class FakeMemoryProvider:
    """Deterministic, network-free provider used by tests and local development."""

    def __init__(self) -> None:
        self._memories: dict[str, tuple[uuid.UUID, str, str]] = {}
        self.calls: list[FakeMemoryProviderCall] = []
        self.fail_next_delete = False

    def create(self, *, user_id: uuid.UUID, category: str, canonical_text: str) -> str:
        external_id = f"fake-memory-{len(self._memories) + 1}"
        self._memories[external_id] = (user_id, category, canonical_text)
        self.calls.append(FakeMemoryProviderCall("create", user_id, external_id))
        return external_id

    def update(self, *, user_id: uuid.UUID, external_id: str, category: str, canonical_text: str) -> None:
        owner = self._memories.get(external_id)
        if owner is None or owner[0] != user_id:
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
        )
        candidates = result.get("results") or result.get("memories") or [result]
        external_id = next((entry.get("id") for entry in candidates if isinstance(entry, dict) and entry.get("id")), None)
        if not isinstance(external_id, str):
            raise RuntimeError("Mem0 create returned no opaque memory id")
        return external_id

    def update(self, *, user_id: uuid.UUID, external_id: str, category: str, canonical_text: str) -> None:
        # user_id is recorded only as metadata; ownership was established by the local ledger.
        self._client.update(external_id, data=canonical_text, metadata={"category": category, "user_id": str(user_id)})

    def delete(self, *, user_id: uuid.UUID, external_id: str) -> None:
        del user_id  # The ledger checked it before this opaque external ID reaches the adapter.
        self._client.delete(external_id)

    def search(self, *, user_id: uuid.UUID, query: str, limit: int) -> list[MemorySearchHit]:
        result = self._client.search(query, user_id=str(user_id), limit=limit)
        entries = result.get("results", result) if isinstance(result, dict) else result
        return [MemorySearchHit(external_id=str(entry["id"]), canonical_text=str(entry.get("memory", ""))) for entry in entries if isinstance(entry, dict) and entry.get("id") and entry.get("memory")]


def create_memory_provider(settings: Settings) -> MemoryProvider:
    if settings.app_env == "test" or settings.memory_provider_mode == "fake":
        return FakeMemoryProvider()
    if settings.memory_provider_mode != "mem0":
        raise ConfigurationError("unsupported memory provider mode")
    if settings.mem0_api_key is None or not settings.mem0_api_key.get_secret_value() or not settings.mem0_endpoint:
        raise ConfigurationError("MEM0_API_KEY and MEM0_ENDPOINT are required for the Mem0 provider")
    return Mem0MemoryProvider(api_key=settings.mem0_api_key.get_secret_value(), endpoint=settings.mem0_endpoint)
