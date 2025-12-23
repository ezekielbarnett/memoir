"""
Authorization system - clean, flexible, minimal overhead.

Design principles:
1. Single decorator/dependency for all auth needs
2. Policy-based access control (not role-based)
3. Project + User + Tier aware
4. Zero boilerplate in route handlers
"""

from memoir.auth.context import AuthContext, get_auth_context
from memoir.auth.policies import (
    require,
    require_any,
    require_all,
    require_auth,
    require_tier,
    require_role,
    Policy,
)
from memoir.auth.capabilities import (
    Capability,
    ProjectRole,
    UserTier,
)
from memoir.auth.jwt import (
    TokenPair,
    UserCreate,
    UserResponse,
    create_token_pair,
    authenticate_user,
    hash_password,
    verify_password,
)
from memoir.auth.routes import router as auth_router

__all__ = [
    # Main interface
    "require",
    "require_any", 
    "require_all",
    "require_auth",
    "require_tier",
    "require_role",
    "AuthContext",
    "get_auth_context",
    # Types
    "Policy",
    "Capability",
    "ProjectRole",
    "UserTier",
    # JWT
    "TokenPair",
    "UserCreate", 
    "UserResponse",
    "create_token_pair",
    "authenticate_user",
    "hash_password",
    "verify_password",
    # Router
    "auth_router",
]

