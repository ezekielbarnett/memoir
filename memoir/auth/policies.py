"""
Policies - the clean interface for route authorization.

This is the magic that makes auth simple in route handlers.
Just use: `ctx: AuthContext = Depends(require("content.read"))`

Design:
- `require()` returns a FastAPI Depends that resolves to AuthContext
- It extracts user from JWT, project from path, checks capability
- If denied, raises 403 automatically
- If allowed, returns AuthContext for the route to use
"""

from __future__ import annotations

from typing import Callable, Any
from functools import wraps

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from memoir.auth.capabilities import Capability, ProjectRole, UserTier
from memoir.auth.context import AuthContext, get_auth_context


# =============================================================================
# JWT Token Handling (pluggable)
# =============================================================================


# Optional JWT bearer (doesn't fail if no token)
optional_bearer = HTTPBearer(auto_error=False)


async def get_user_from_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
) -> str | None:
    """
    Extract user_id from JWT token.
    
    Handles:
    - Real JWT tokens (validated with secret)
    - Dev tokens in format "user_{id}" (for testing)
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # Try real JWT validation first
    try:
        from memoir.auth.jwt import decode_token, TokenError
        payload = decode_token(token, expected_type="access")
        return payload.sub
    except TokenError:
        pass  # Fall through to dev mode
    except ImportError:
        pass  # JWT module not available
    
    # Dev mode: accept simple tokens like "user_123" or "dev_user_abc"
    # Only in non-production!
    from memoir.config import get_settings
    settings = get_settings()
    
    if not settings.is_production:
        if token.startswith("user_") or token.startswith("dev_"):
            return token
        # Also accept just an ID for quick testing
        if len(token) < 50 and not token.startswith("ey"):  # Not a JWT
            return f"user_{token}"
    
    return None


# =============================================================================
# Policy - the core authorization type
# =============================================================================


class Policy:
    """
    A policy that can be checked.
    
    Policies are composable:
        require("content.read")  # Single capability
        require_any("content.read", "content.edit")  # Any of these
        require_all("content.edit", "projection.edit")  # All of these
    """
    
    def __init__(
        self,
        capabilities: list[Capability | str] | None = None,
        require_all: bool = True,
        require_auth: bool = True,
        require_project: bool = False,
        min_tier: UserTier | None = None,
        min_role: ProjectRole | None = None,
        custom_check: Callable[[AuthContext], bool] | None = None,
    ):
        self.capabilities = capabilities or []
        self.require_all_caps = require_all
        self.require_auth = require_auth
        self.require_project = require_project
        self.min_tier = min_tier
        self.min_role = min_role
        self.custom_check = custom_check
    
    def check(self, ctx: AuthContext) -> tuple[bool, str | None]:
        """
        Check if context satisfies this policy.
        
        Returns: (allowed, error_message)
        """
        # Auth required?
        if self.require_auth and ctx.is_anonymous:
            return False, "Authentication required"
        
        # Project required?
        if self.require_project and not ctx.project_id:
            return False, "Project context required"
        
        # Tier check
        if self.min_tier:
            tier_order = [UserTier.FREE, UserTier.PRO, UserTier.ENTERPRISE]
            user_level = tier_order.index(ctx.user_tier)
            min_level = tier_order.index(self.min_tier)
            if user_level < min_level:
                return False, f"Requires {self.min_tier.value} tier or higher"
        
        # Role check (if in project context)
        if self.min_role and ctx.project_id:
            role_order = [
                ProjectRole.VIEWER,
                ProjectRole.CONTRIBUTOR,
                ProjectRole.EDITOR,
                ProjectRole.ADMIN,
                ProjectRole.OWNER,
            ]
            if ctx.project_role is None:
                return False, "No access to this project"
            user_level = role_order.index(ctx.project_role)
            min_level = role_order.index(self.min_role)
            if user_level < min_level:
                return False, f"Requires {self.min_role.value} role or higher"
        
        # Capability check
        if self.capabilities:
            if self.require_all_caps:
                if not ctx.can_all(*self.capabilities):
                    missing = [c for c in self.capabilities if not ctx.can(c)]
                    return False, f"Missing permissions: {missing}"
            else:
                if not ctx.can_any(*self.capabilities):
                    return False, f"Requires one of: {self.capabilities}"
        
        # Custom check
        if self.custom_check and not self.custom_check(ctx):
            return False, "Custom policy check failed"
        
        return True, None


# =============================================================================
# Main Interface - the require() function
# =============================================================================


def require(
    *capabilities: Capability | str,
    require_auth: bool = True,
    require_project: bool | None = None,  # Auto-detect from route
    min_tier: UserTier | None = None,
    min_role: ProjectRole | None = None,
) -> Callable:
    """
    Require capabilities to access a route.
    
    Usage:
        @app.get("/projects/{project_id}/content")
        async def get_content(
            project_id: str,
            ctx: AuthContext = Depends(require("content.read")),
        ):
            # ctx is fully populated if we get here
            return {"user": ctx.user_id, "can_edit": ctx.can("content.edit")}
    
    Args:
        *capabilities: Capabilities required (all must be present)
        require_auth: If True, anonymous access is denied
        require_project: If True, project_id must be in path
        min_tier: Minimum subscription tier required
        min_role: Minimum project role required
    
    Returns:
        FastAPI Depends that resolves to AuthContext
    """
    policy = Policy(
        capabilities=list(capabilities),
        require_all=True,
        require_auth=require_auth,
        require_project=require_project if require_project is not None else bool(capabilities),
        min_tier=min_tier,
        min_role=min_role,
    )
    
    return _create_dependency(policy)


def require_any(*capabilities: Capability | str, **kwargs) -> Callable:
    """Require ANY of the listed capabilities."""
    policy = Policy(
        capabilities=list(capabilities),
        require_all=False,
        **kwargs
    )
    return _create_dependency(policy)


def require_all(*capabilities: Capability | str, **kwargs) -> Callable:
    """Require ALL of the listed capabilities (same as require)."""
    return require(*capabilities, **kwargs)


def require_auth() -> Callable:
    """Just require authentication, no specific capability."""
    return require(require_auth=True, require_project=False)


def require_tier(tier: UserTier) -> Callable:
    """Require a minimum subscription tier."""
    return require(min_tier=tier, require_project=False)


def require_role(role: ProjectRole) -> Callable:
    """Require a minimum project role."""
    return require(min_role=role, require_project=True)


# =============================================================================
# Internal: Create the FastAPI Dependency
# =============================================================================


def _create_dependency(policy: Policy) -> Callable:
    """Create a FastAPI Depends from a policy."""
    
    async def dependency(
        request: Request,
        user_id: str | None = Depends(get_user_from_token),
    ) -> AuthContext:
        # Extract project_id from path if present
        project_id = request.path_params.get("project_id")
        
        # Get storage from app state (if available)
        storage = getattr(request.app.state, "storage", None)
        
        # Build context
        ctx = await get_auth_context(
            user_id=user_id,
            project_id=project_id,
            storage=storage,
        )
        
        # Check policy
        allowed, error = policy.check(ctx)
        if not allowed:
            raise HTTPException(status_code=403, detail=error)
        
        return ctx
    
    return dependency


# =============================================================================
# Optional: Decorator style (alternative to Depends)
# =============================================================================


def authorized(*capabilities: Capability | str, **kwargs):
    """
    Decorator alternative to Depends(require(...)).
    
    Usage:
        @app.get("/projects/{project_id}")
        @authorized("project.read")
        async def get_project(project_id: str, ctx: AuthContext):
            ...
    
    Note: The Depends() style is preferred for FastAPI.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kw):
            # Get the request from kwargs (FastAPI injects it)
            request = kw.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request:
                dep = require(*capabilities, **kwargs)
                ctx = await dep(request)
                kw["ctx"] = ctx
            
            return await func(*args, **kw)
        return wrapper
    return decorator

