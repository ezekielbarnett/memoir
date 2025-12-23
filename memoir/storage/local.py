"""
Local storage implementations for development.

These are in-memory or filesystem-based implementations
that work without any external services.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, AsyncIterator
from datetime import datetime, timezone
import uuid

from memoir.storage.base import (
    ContentStorage,
    MetadataStorage,
    CacheStorage,
    QueueStorage,
    StorageProvider,
)


# =============================================================================
# Local Filesystem Content Storage
# =============================================================================


class LocalContentStorage(ContentStorage):
    """Store content on local filesystem."""
    
    def __init__(self, base_path: str = "./data/content"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _key_to_path(self, key: str) -> Path:
        return self.base_path / key
    
    async def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._key_to_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)
    
    async def get(self, key: str) -> bytes:
        path = self._key_to_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Content not found: {key}")
        return path.read_bytes()
    
    async def delete(self, key: str) -> bool:
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        # For local, just return the file path
        return f"file://{self._key_to_path(key).absolute()}"
    
    async def list_keys(self, prefix: str = "") -> AsyncIterator[str]:
        search_path = self.base_path / prefix if prefix else self.base_path
        if search_path.exists():
            for path in search_path.rglob("*"):
                if path.is_file():
                    yield str(path.relative_to(self.base_path))


# =============================================================================
# In-Memory Metadata Storage
# =============================================================================


class InMemoryMetadataStorage(MetadataStorage):
    """In-memory document storage for development."""
    
    def __init__(self):
        self._data: dict[str, dict[str, dict[str, Any]]] = {}
    
    async def save(self, collection: str, id: str, data: dict[str, Any]) -> None:
        if collection not in self._data:
            self._data[collection] = {}
        self._data[collection][id] = {
            **data,
            "_id": id,
            "_updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get(self, collection: str, id: str) -> dict[str, Any] | None:
        return self._data.get(collection, {}).get(id)
    
    async def delete(self, collection: str, id: str) -> bool:
        if collection in self._data and id in self._data[collection]:
            del self._data[collection][id]
            return True
        return False
    
    async def query(
        self,
        collection: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if collection not in self._data:
            return []
        
        results = list(self._data[collection].values())
        
        # Apply filters
        if filters:
            filtered = []
            for doc in results:
                match = True
                for key, value in filters.items():
                    if doc.get(key) != value:
                        match = False
                        break
                if match:
                    filtered.append(doc)
            results = filtered
        
        # Apply pagination
        return results[offset:offset + limit]
    
    async def update(self, collection: str, id: str, updates: dict[str, Any]) -> bool:
        if collection in self._data and id in self._data[collection]:
            self._data[collection][id].update(updates)
            self._data[collection][id]["_updated_at"] = datetime.now(timezone.utc).isoformat()
            return True
        return False


# =============================================================================
# In-Memory Cache Storage
# =============================================================================


class InMemoryCacheStorage(CacheStorage):
    """In-memory cache for development."""
    
    def __init__(self):
        self._cache: dict[str, tuple[Any, datetime | None]] = {}
    
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires_at = None
        if ttl:
            expires_at = datetime.now(timezone.utc).timestamp() + ttl
        self._cache[key] = (value, expires_at)
    
    async def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        
        value, expires_at = self._cache[key]
        if expires_at and datetime.now(timezone.utc).timestamp() > expires_at:
            del self._cache[key]
            return None
        
        return value
    
    async def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None


# =============================================================================
# In-Memory Queue Storage
# =============================================================================


class InMemoryQueueStorage(QueueStorage):
    """In-memory queue for development."""
    
    def __init__(self):
        self._queues: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        self._pending: dict[str, dict[str, dict[str, Any]]] = {}
    
    async def enqueue(self, queue_name: str, message: dict[str, Any]) -> str:
        if queue_name not in self._queues:
            self._queues[queue_name] = []
        
        message_id = str(uuid.uuid4())
        self._queues[queue_name].append((message_id, message))
        return message_id
    
    async def dequeue(self, queue_name: str, wait_seconds: int = 0) -> dict[str, Any] | None:
        if queue_name not in self._queues or not self._queues[queue_name]:
            return None
        
        message_id, message = self._queues[queue_name].pop(0)
        
        # Track pending for ack
        if queue_name not in self._pending:
            self._pending[queue_name] = {}
        self._pending[queue_name][message_id] = message
        
        return {"_message_id": message_id, **message}
    
    async def ack(self, queue_name: str, message_id: str) -> None:
        if queue_name in self._pending and message_id in self._pending[queue_name]:
            del self._pending[queue_name][message_id]


# =============================================================================
# Factory
# =============================================================================


def create_local_storage(data_dir: str = "./data") -> StorageProvider:
    """Create a StorageProvider with local implementations."""
    return StorageProvider(
        content=LocalContentStorage(f"{data_dir}/content"),
        metadata=InMemoryMetadataStorage(),
        cache=InMemoryCacheStorage(),
        queue=InMemoryQueueStorage(),
    )

