"""
Capabilities, roles, and tiers.

This defines WHAT users can do, not HOW we check it.
The actual checking happens in policies.py.
"""

from enum import Enum
from typing import Any


class ProjectRole(str, Enum):
    """Role a user has within a specific project."""
    
    OWNER = "owner"          # Full control, can delete project
    ADMIN = "admin"          # Can manage contributors, settings
    EDITOR = "editor"        # Can edit content and projections
    CONTRIBUTOR = "contributor"  # Can add content only
    VIEWER = "viewer"        # Read-only access


class UserTier(str, Enum):
    """Platform-wide subscription tier."""
    
    FREE = "free"            # Basic features
    PRO = "pro"              # Advanced features
    ENTERPRISE = "enterprise"  # All features + priority support


class Capability(str, Enum):
    """
    Fine-grained capabilities.
    
    These are the actual permissions checked by policies.
    A user's capabilities are derived from their role + tier.
    """
    
    # Project-level
    PROJECT_READ = "project.read"
    PROJECT_EDIT = "project.edit"
    PROJECT_DELETE = "project.delete"
    PROJECT_MANAGE_CONTRIBUTORS = "project.manage_contributors"
    
    # Content
    CONTENT_READ = "content.read"
    CONTENT_CREATE = "content.create"
    CONTENT_EDIT = "content.edit"
    CONTENT_DELETE = "content.delete"
    
    # Projections (documents)
    PROJECTION_READ = "projection.read"
    PROJECTION_CREATE = "projection.create"
    PROJECTION_EDIT = "projection.edit"
    PROJECTION_LOCK = "projection.lock"
    PROJECTION_EXPORT = "projection.export"
    
    # Advanced features (tier-gated)
    AI_GENERATION = "ai.generation"
    AI_ADVANCED = "ai.advanced"           # Pro+ only
    MULTI_PROJECTION = "multi.projection"  # Multiple projections per project
    EXPORT_PDF = "export.pdf"
    EXPORT_PRINT = "export.print"         # Pro+ only
    API_ACCESS = "api.access"             # Enterprise only
    
    # Admin
    ADMIN_USERS = "admin.users"
    ADMIN_BILLING = "admin.billing"


# =============================================================================
# Capability Mappings
# =============================================================================


# What capabilities each project role grants
ROLE_CAPABILITIES: dict[ProjectRole, set[Capability]] = {
    ProjectRole.OWNER: {
        Capability.PROJECT_READ,
        Capability.PROJECT_EDIT,
        Capability.PROJECT_DELETE,
        Capability.PROJECT_MANAGE_CONTRIBUTORS,
        Capability.CONTENT_READ,
        Capability.CONTENT_CREATE,
        Capability.CONTENT_EDIT,
        Capability.CONTENT_DELETE,
        Capability.PROJECTION_READ,
        Capability.PROJECTION_CREATE,
        Capability.PROJECTION_EDIT,
        Capability.PROJECTION_LOCK,
        Capability.PROJECTION_EXPORT,
    },
    ProjectRole.ADMIN: {
        Capability.PROJECT_READ,
        Capability.PROJECT_EDIT,
        Capability.PROJECT_MANAGE_CONTRIBUTORS,
        Capability.CONTENT_READ,
        Capability.CONTENT_CREATE,
        Capability.CONTENT_EDIT,
        Capability.CONTENT_DELETE,
        Capability.PROJECTION_READ,
        Capability.PROJECTION_CREATE,
        Capability.PROJECTION_EDIT,
        Capability.PROJECTION_LOCK,
        Capability.PROJECTION_EXPORT,
    },
    ProjectRole.EDITOR: {
        Capability.PROJECT_READ,
        Capability.CONTENT_READ,
        Capability.CONTENT_CREATE,
        Capability.CONTENT_EDIT,
        Capability.PROJECTION_READ,
        Capability.PROJECTION_CREATE,
        Capability.PROJECTION_EDIT,
        Capability.PROJECTION_LOCK,
        Capability.PROJECTION_EXPORT,
    },
    ProjectRole.CONTRIBUTOR: {
        Capability.PROJECT_READ,
        Capability.CONTENT_READ,
        Capability.CONTENT_CREATE,
        Capability.PROJECTION_READ,
    },
    ProjectRole.VIEWER: {
        Capability.PROJECT_READ,
        Capability.CONTENT_READ,
        Capability.PROJECTION_READ,
    },
}


# What capabilities each tier grants (additive to role)
TIER_CAPABILITIES: dict[UserTier, set[Capability]] = {
    UserTier.FREE: {
        Capability.AI_GENERATION,
        Capability.EXPORT_PDF,
    },
    UserTier.PRO: {
        Capability.AI_GENERATION,
        Capability.AI_ADVANCED,
        Capability.MULTI_PROJECTION,
        Capability.EXPORT_PDF,
        Capability.EXPORT_PRINT,
    },
    UserTier.ENTERPRISE: {
        Capability.AI_GENERATION,
        Capability.AI_ADVANCED,
        Capability.MULTI_PROJECTION,
        Capability.EXPORT_PDF,
        Capability.EXPORT_PRINT,
        Capability.API_ACCESS,
        Capability.ADMIN_USERS,
        Capability.ADMIN_BILLING,
    },
}


def get_capabilities(
    role: ProjectRole | None = None,
    tier: UserTier = UserTier.FREE,
) -> set[Capability]:
    """
    Get all capabilities for a role + tier combination.
    
    Role capabilities are project-specific.
    Tier capabilities are platform-wide additions.
    """
    caps: set[Capability] = set()
    
    if role:
        caps.update(ROLE_CAPABILITIES.get(role, set()))
    
    caps.update(TIER_CAPABILITIES.get(tier, set()))
    
    return caps


def has_capability(
    capability: Capability | str,
    role: ProjectRole | None = None,
    tier: UserTier = UserTier.FREE,
) -> bool:
    """Check if a role+tier combination has a specific capability."""
    if isinstance(capability, str):
        capability = Capability(capability)
    
    return capability in get_capabilities(role, tier)

