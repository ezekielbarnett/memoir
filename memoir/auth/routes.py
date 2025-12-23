# =============================================================================
# Auth API Routes
# =============================================================================
#
# Endpoints:
#   POST /auth/register     - Create account
#   POST /auth/login        - Get tokens
#   POST /auth/refresh      - Refresh tokens
#   POST /auth/logout       - Invalidate tokens (placeholder)
#   GET  /auth/me           - Get current user
#   POST /auth/verify-email - Verify email address
#   POST /auth/forgot-password - Request password reset
#   POST /auth/reset-password  - Reset password with token
#
# OAuth:
#   GET  /auth/providers           - List available OAuth providers
#   GET  /auth/{provider}/authorize - Get OAuth redirect URL
#   POST /auth/{provider}/callback  - Complete OAuth flow
#
# =============================================================================

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from memoir.auth.jwt import (
    UserCreate,
    UserResponse,
    UserInDB,
    TokenPair,
    create_user,
    authenticate_user,
    get_user_by_id,
    get_user_by_email,
    create_token_pair,
    refresh_tokens,
    create_verification_token,
    verify_email_token,
    create_password_reset_token,
    reset_password,
    TokenExpiredError,
    TokenInvalidError,
    _users_db,
    _users_by_email,
)
from memoir.auth.policies import require, get_user_from_token
from memoir.auth.context import AuthContext
from memoir.core.utils import generate_id, utc_now
from memoir.integrations.email import send_welcome_email, send_password_reset_email
from memoir.integrations.oauth import get_oauth_manager, OAuthError, OAuthUserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


# =============================================================================
# Request/Response Models
# =============================================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


# =============================================================================
# Public Endpoints
# =============================================================================

@router.post("/register", response_model=TokenPair)
async def register(data: UserCreate):
    """
    Create a new account.
    
    Returns access and refresh tokens on success.
    """
    try:
        user = create_user(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create verification token and send welcome email
    verification_token = create_verification_token(user.id)
    await send_welcome_email(user.email, user.name, verification_token)
    
    # Return tokens immediately (email verification can be done later)
    return create_token_pair(user.id, {"email": user.email, "tier": user.tier})


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest):
    """
    Authenticate and get tokens.
    """
    user = authenticate_user(data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    return create_token_pair(user.id, {"email": user.email, "tier": user.tier})


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest):
    """
    Use refresh token to get new access token.
    """
    try:
        return refresh_tokens(data.refresh_token)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Refresh token expired, please login again")
    except TokenInvalidError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def logout():
    """
    Logout (client should discard tokens).
    
    Note: For full security, implement token blacklisting with Redis.
    """
    # TODO: Add refresh token to blacklist in Redis/DB
    return {"message": "Logged out successfully"}


@router.post("/verify-email")
async def verify_email(data: VerifyEmailRequest):
    """
    Verify email address using token from email.
    """
    user_id = verify_email_token(data.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    
    return {"message": "Email verified successfully"}


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """
    Request password reset email.
    
    Always returns success to prevent email enumeration.
    """
    token = create_password_reset_token(data.email)
    
    if token:
        await send_password_reset_email(data.email, token)
    
    # Always return success to prevent email enumeration
    return {"message": "If an account exists with this email, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password_endpoint(data: ResetPasswordRequest):
    """
    Reset password using token from email.
    """
    success = reset_password(data.token, data.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    return {"message": "Password reset successfully"}


# =============================================================================
# Protected Endpoints
# =============================================================================

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    ctx: AuthContext = Depends(require(require_project=False)),
):
    """
    Get the current authenticated user.
    """
    user = get_user_by_id(ctx.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        tier=user.tier,
        email_verified=user.email_verified,
        created_at=user.created_at,
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    name: str | None = None,
    ctx: AuthContext = Depends(require(require_project=False)),
):
    """
    Update the current user's profile.
    """
    user = get_user_by_id(ctx.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if name:
        user.name = name
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        tier=user.tier,
        email_verified=user.email_verified,
        created_at=user.created_at,
    )


# =============================================================================
# OAuth Endpoints
# =============================================================================

class OAuthCallbackRequest(BaseModel):
    code: str
    state: str | None = None


@router.get("/providers")
async def list_oauth_providers():
    """
    List available OAuth providers.
    
    Only returns providers that are properly configured.
    """
    oauth = get_oauth_manager()
    return {
        "providers": oauth.get_available_providers(),
        "note": "Configure providers via environment variables. See DEPLOY.md."
    }


@router.get("/{provider}/authorize")
async def oauth_authorize(provider: str):
    """
    Get the OAuth authorization URL.
    
    Redirect the user to this URL to start the OAuth flow.
    """
    oauth = get_oauth_manager()
    
    if provider not in oauth.get_available_providers():
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' not available. Configured: {oauth.get_available_providers()}"
        )
    
    try:
        url = oauth.get_authorize_url(provider)
        return {"authorize_url": url}
    except OAuthError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider}/callback", response_model=TokenPair)
async def oauth_callback(provider: str, data: OAuthCallbackRequest):
    """
    Complete the OAuth flow.
    
    Exchange the authorization code for user info and return JWT tokens.
    """
    oauth = get_oauth_manager()
    
    # Validate state (CSRF protection)
    if data.state:
        expected_provider = oauth.validate_state(data.state)
        if expected_provider != provider:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    try:
        # Get user info from OAuth provider
        oauth_user = await oauth.authenticate(provider, data.code)
        
        # Find or create user
        user = _find_or_create_oauth_user(oauth_user)
        
        # Return tokens
        return create_token_pair(user.id, {"email": user.email, "tier": user.tier})
        
    except OAuthError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _find_or_create_oauth_user(oauth_user: OAuthUserInfo) -> UserInDB:
    """
    Find existing user or create new one from OAuth info.
    
    Handles account linking: if email exists, link OAuth to that account.
    """
    # Check if user exists by email
    existing = get_user_by_email(oauth_user.email)
    
    if existing:
        # Link OAuth provider to existing account
        if oauth_user.provider == "google" and not existing.google_id:
            existing.google_id = oauth_user.provider_user_id
        # Add more providers as needed
        existing.updated_at = utc_now()
        return existing
    
    # Create new user
    now = utc_now()
    user = UserInDB(
        id=generate_id("user"),
        email=oauth_user.email,
        name=oauth_user.name,
        password_hash="",  # No password for OAuth-only users
        email_verified=oauth_user.email_verified,
        google_id=oauth_user.provider_user_id if oauth_user.provider == "google" else None,
        created_at=now,
        updated_at=now,
    )
    
    # Save to "database"
    _users_db[user.id] = user
    _users_by_email[user.email] = user.id
    
    return user

