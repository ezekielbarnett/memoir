"""
Core module - fundamental data models and infrastructure.

This module contains:
- models: Core data models (Project, Contributor, ContentItem)
- projections: Document projection system (DocumentProjection, NarrativeContext)
- events: Event system for pub/sub communication
- registry: Service and resource registry
- utils: Shared utility functions
"""

from memoir.core.models import (
    Project,
    Contributor,
    ContentItem,
    ContentType,
    ProjectStatus,
    ContributorStatus,
    ContributorRole,
    PhaseStatus,
    Subject,
    PhaseProgress,
    User,
)

from memoir.core.projections import (
    DocumentProjection,
    ProjectedSection,
    ContentPool,
    ProjectionConfig,
    ProjectionStyle,
    ProjectionLength,
    SectionState,
    UpdateMode,
    MergeStrategy,
    NarrativeContext,
    DiscoveredTheme,
)

from memoir.core.events import (
    Event,
    EventBus,
    get_event_bus,
    reset_event_bus,
)

from memoir.core.registry import (
    Registry,
    get_registry,
    reset_registry,
)

from memoir.core.utils import (
    generate_id,
    utc_now,
)

__all__ = [
    # Models
    "Project",
    "Contributor",
    "ContentItem",
    "ContentType",
    "ProjectStatus",
    "ContributorStatus",
    "ContributorRole",
    "PhaseStatus",
    "Subject",
    "PhaseProgress",
    "User",
    # Projections
    "DocumentProjection",
    "ProjectedSection",
    "ContentPool",
    "ProjectionConfig",
    "ProjectionStyle",
    "ProjectionLength",
    "SectionState",
    "UpdateMode",
    "MergeStrategy",
    "NarrativeContext",
    "DiscoveredTheme",
    # Events
    "Event",
    "EventBus",
    "get_event_bus",
    "reset_event_bus",
    # Registry
    "Registry",
    "get_registry",
    "reset_registry",
    # Utils
    "generate_id",
    "utc_now",
]
