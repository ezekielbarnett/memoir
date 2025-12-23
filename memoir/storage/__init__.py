"""
Storage abstractions.

AWS Integration Points:
- ContentStorage → S3 (audio, images, PDFs)
- MetadataStorage → RDS/Aurora PostgreSQL or DynamoDB
- CacheStorage → ElastiCache (Redis)
- QueueStorage → SQS
"""

from memoir.storage.base import (
    ContentStorage,
    MetadataStorage,
    CacheStorage,
    QueueStorage,
    StorageProvider,
    Collections,
)
from memoir.storage.local import create_local_storage

__all__ = [
    "ContentStorage",
    "MetadataStorage",
    "CacheStorage",
    "QueueStorage",
    "StorageProvider",
    "Collections",
    "create_local_storage",
]
