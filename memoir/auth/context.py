"""
Auth context - the "who can do what" for each request.

This is the lightweight object passed to route handlers.
It contains everything needed to make authorization decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memoir.auth.capabilities import (
    Capability,
    ProjectRole,
    UserTier,
    get_capabilities,
)


@dataclass
class AuthContext:
    """
    Authorization context for a request.
    
    This is the single object that tells you everything about
    what the current user can do in the current context.
    
    Usage in routes:
        async def my_route(ctx: AuthContext = Depends(require("content.read"))):
            print(f"User {ctx.user_id} accessing project {ctx.project_id}")
            if ctx.can("content.edit"):
                # do something
    """
    
    # Who
    user_id: str | None = None
    user_email: str | None = None
    user_tier: UserTier = UserTier.FREE
    
    # What project (if applicable)
    project_id: str | None = None
    project_role: ProjectRole | None = None
    
    # Contributor context (if applicable)
    contributor_id: str | None = None
    
    # Computed capabilities (cached)
    _capabilities: set[Capability] = field(default_factory=set, repr=False)
    
    # Extra context
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Compute capabilities from role + tier."""
        self._capabilities = get_capabilities(self.project_role, self.user_tier)
    
    @property
    def is_authenticated(self) -> bool:
        """Is there a logged-in user?"""
        return self.user_id is not None
    
    @property
    def is_anonymous(self) -> bool:
        """Is this an anonymous request?"""
        return self.user_id is None
    
    @property
    def is_owner(self) -> bool:
        """Is the user the project owner?"""
        return self.project_role == ProjectRole.OWNER
    
    @property
    def capabilities(self) -> set[Capability]:
        """All capabilities this user has in this context."""
        return self._capabilities
    
    def can(self, capability: Capability | str) -> bool:
        """
        Check if user has a capability.
        
        Usage:
            if ctx.can("content.edit"):
                # do something
            if ctx.can(Capability.PROJECTION_LOCK):
                # do something
        """
        if isinstance(capability, str):
            try:
                capability = Capability(capability)
            except ValueError:
                return False
        return capability in self._capabilities
    
    def can_any(self, *capabilities: Capability | str) -> bool:
        """Check if user has ANY of the capabilities."""
        return any(self.can(c) for c in capabilities)
    
    def can_all(self, *capabilities: Capability | str) -> bool:
        """Check if user has ALL of the capabilities."""
        return all(self.can(c) for c in capabilities)
    
    def require(self, capability: Capability | str) -> None:
        """
        Raise if user doesn't have capability.
        
        Usage:
            ctx.require("content.edit")  # raises if not allowed
        """
        if not self.can(capability):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {capability}"
            )
    
    @classmethod
    def anonymous(cls) -> AuthContext:
        """Create an anonymous context (no user)."""
        return cls()
    
    @classmethod
    def system(cls) -> AuthContext:
        """Create a system context (full access for internal operations)."""
        ctx = cls(user_id="__system__", user_tier=UserTier.ENTERPRISE)
        ctx._capabilities = set(Capability)  # All capabilities
        return ctx


# =============================================================================
# Context Resolution (how we figure out the context for a request)
# =============================================================================


async def get_auth_context(
    user_id: str | None = None,
    project_id: str | None = None,
    storage=None,
) -> AuthContext:
    """
    Resolve the full auth context for a request.
    
    This is the main function that looks up:
    1. User info (from session/JWT)
    2. User's tier (from subscription)
    3. User's role in the project (from project membership)
    
    In production, this queries the database.
    For now, it's a stub that can be replaced.
    """
    if not user_id:
        return AuthContext.anonymous()
    
    # Get user info
    user_tier = UserTier.FREE
    user_email = None
    
    if storage:
        user_data = await storage.metadata.get("users", user_id)
        if user_data:
            user_tier = UserTier(user_data.get("tier", "free"))
            user_email = user_data.get("email")
    
    # Get project role if project specified
    project_role = None
    contributor_id = None
    
    if project_id and storage:
        # Check if user owns the project
        project_data = await storage.metadata.get("projects", project_id)
        if project_data and project_data.get("owner_id") == user_id:
            project_role = ProjectRole.OWNER
        else:
            # Check contributor/member table
            members = await storage.metadata.query(
                "project_members",
                {"project_id": project_id, "user_id": user_id}
            )
            if members:
                member = members[0]
                project_role = ProjectRole(member.get("role", "viewer"))
                contributor_id = member.get("contributor_id")
    
    return AuthContext(
        user_id=user_id,
        user_email=user_email,
        user_tier=user_tier,
        project_id=project_id,
        project_role=project_role,
        contributor_id=contributor_id,
    )

