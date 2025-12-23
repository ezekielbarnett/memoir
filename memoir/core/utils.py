"""
Shared utility functions for the memoir platform.

This module contains common utilities used across the codebase.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID with optional prefix.
    
    Args:
        prefix: Optional prefix (e.g., "proj", "content", "sec")
        
    Returns:
        A unique ID like "proj_a1b2c3d4e5f6"
    """
    uid = str(uuid.uuid4())[:12]
    return f"{prefix}_{uid}" if prefix else uid


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)

