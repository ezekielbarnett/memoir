"""
Storage abstraction layer.

All persistence goes through these interfaces. This allows swapping
implementations (local filesystem → S3, SQLite → PostgreSQL, etc.)
without changing application code.

AWS Integration Points:
- ContentStorage → S3
- MetadataStorage → PostgreSQL (RDS/Aurora) or DynamoDB
- CacheStorage → ElastiCache (Redis)
- QueueStorage → SQS (for async jobs)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
from datetime import datetime

from pydantic import BaseModel


# =============================================================================
# Storage Interfaces
# =============================================================================


class ContentStorage(ABC):
    """
    Storage for binary content (audio, images, PDFs).
    
    AWS Implementation: S3
    Local Implementation: Filesystem
    """
    
    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store content, return URL/path."""
        pass
    
    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Retrieve content by key."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete content."""
        pass
    
    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Get a signed URL for direct access."""
        pass
    
    @abstractmethod
    async def list_keys(self, prefix: str = "") -> AsyncIterator[str]:
        """List keys with optional prefix."""
        pass


class MetadataStorage(ABC):
    """
    Storage for structured data (projects, contributors, content items).
    
    AWS Implementation: PostgreSQL via RDS/Aurora, or DynamoDB
    Local Implementation: SQLite or in-memory
    """
    
    @abstractmethod
    async def save(self, collection: str, id: str, data: dict[str, Any]) -> None:
        """Save a document to a collection."""
        pass
    
    @abstractmethod
    async def get(self, collection: str, id: str) -> dict[str, Any] | None:
        """Get a document by ID."""
        pass
    
    @abstractmethod
    async def delete(self, collection: str, id: str) -> bool:
        """Delete a document."""
        pass
    
    @abstractmethod
    async def query(
        self,
        collection: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query documents with optional filters."""
        pass
    
    @abstractmethod
    async def update(self, collection: str, id: str, updates: dict[str, Any]) -> bool:
        """Partial update of a document."""
        pass


class CacheStorage(ABC):
    """
    Fast key-value cache for sessions, tokens, frequently accessed data.
    
    AWS Implementation: ElastiCache (Redis)
    Local Implementation: In-memory dict or local Redis
    """
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set a value with optional TTL in seconds."""
        pass
    
    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get a value."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass


class QueueStorage(ABC):
    """
    Message queue for async job processing.
    
    AWS Implementation: SQS
    Local Implementation: In-memory queue or local Redis
    """
    
    @abstractmethod
    async def enqueue(self, queue_name: str, message: dict[str, Any]) -> str:
        """Add a message to queue, return message ID."""
        pass
    
    @abstractmethod
    async def dequeue(self, queue_name: str, wait_seconds: int = 0) -> dict[str, Any] | None:
        """Get next message from queue."""
        pass
    
    @abstractmethod
    async def ack(self, queue_name: str, message_id: str) -> None:
        """Acknowledge message processing complete."""
        pass


# =============================================================================
# Storage Provider (dependency injection container)
# =============================================================================


class StorageProvider(BaseModel):
    """
    Container for all storage backends.
    
    Initialize once at app startup with appropriate implementations.
    Services receive this and use the interfaces without knowing
    the underlying implementation.
    """
    
    model_config = {"arbitrary_types_allowed": True}
    
    content: ContentStorage
    metadata: MetadataStorage
    cache: CacheStorage
    queue: QueueStorage


# =============================================================================
# Collection Names (for MetadataStorage)
# =============================================================================


class Collections:
    """Standard collection/table names."""
    
    PROJECTS = "projects"
    CONTRIBUTORS = "contributors"
    CONTENT_ITEMS = "content_items"
    PROJECTIONS = "projections"
    USERS = "users"
    SESSIONS = "sessions"
    NOTIFICATIONS = "notifications"

