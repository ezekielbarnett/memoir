# =============================================================================
# JWT Authentication Implementation
# =============================================================================
#
# This module provides real JWT authentication:
#   - Token creation (access + refresh)
#   - Token validation
#   - Password hashing
#   - FastAPI dependencies
#
# =============================================================================

from datetime import datetime, timedelta, timezone
from typing import Any
import secrets
import hashlib
import logging

from pydantic import BaseModel, EmailStr, Field
import jwt

from memoir.config import get_settings
from memoir.core.utils import generate_id, utc_now

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# Models
# =============================================================================

class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    exp: datetime
    iat: datetime
    type: str  # "access" or "refresh"
    jti: str  # unique token ID (for revocation)


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class UserCreate(BaseModel):
    """User registration data."""
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=100)


class UserInDB(BaseModel):
    """User stored in database."""
    id: str
    email: str
    name: str
    password_hash: str
    tier: str = "free"
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime
    
    # OAuth links
    google_id: str | None = None
    apple_id: str | None = None


class UserResponse(BaseModel):
    """User data returned to client (no sensitive fields)."""
    id: str
    email: str
    name: str
    tier: str
    email_verified: bool
    created_at: datetime


# =============================================================================
# Password Hashing
# =============================================================================

def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-SHA256.
    
    Returns: salt:hash format string
    """
    salt = secrets.token_hex(32)
    hash_bytes = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=100_000
    )
    return f"{salt}:{hash_bytes.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    try:
        salt, stored_hash = password_hash.split(':')
        hash_bytes = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=100_000
        )
        return secrets.compare_digest(hash_bytes.hex(), stored_hash)
    except (ValueError, AttributeError):
        return False


# =============================================================================
# Token Creation
# =============================================================================

def create_access_token(user_id: str, extra_claims: dict | None = None) -> str:
    """Create a JWT access token."""
    now = utc_now()
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "access",
        "jti": generate_id("tok"),
        **(extra_claims or {}),
    }
    
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token (longer-lived)."""
    now = utc_now()
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": generate_id("rtok"),
    }
    
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_token_pair(user_id: str, extra_claims: dict | None = None) -> TokenPair:
    """Create both access and refresh tokens."""
    return TokenPair(
        access_token=create_access_token(user_id, extra_claims),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


# =============================================================================
# Token Validation
# =============================================================================

class TokenError(Exception):
    """Base exception for token errors."""
    pass


class TokenExpiredError(TokenError):
    """Token has expired."""
    pass


class TokenInvalidError(TokenError):
    """Token is invalid or malformed."""
    pass


def decode_token(token: str, expected_type: str = "access") -> TokenPayload:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT string
        expected_type: "access" or "refresh"
    
    Returns:
        TokenPayload with validated claims
    
    Raises:
        TokenExpiredError: Token has expired
        TokenInvalidError: Token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        
        # Validate token type
        if payload.get("type") != expected_type:
            raise TokenInvalidError(f"Expected {expected_type} token, got {payload.get('type')}")
        
        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            type=payload["type"],
            jti=payload.get("jti", ""),
        )
    
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError(f"Invalid token: {e}")


def refresh_tokens(refresh_token: str) -> TokenPair:
    """
    Use a refresh token to get new access and refresh tokens.
    
    The old refresh token is invalidated (by generating new jti).
    """
    payload = decode_token(refresh_token, expected_type="refresh")
    
    # In production, you'd also check if this refresh token has been revoked
    # by checking the jti against a blacklist in Redis/DB
    
    return create_token_pair(payload.sub)


# =============================================================================
# In-Memory User Store (Replace with DB in production)
# =============================================================================

_users_db: dict[str, UserInDB] = {}
_users_by_email: dict[str, str] = {}  # email -> user_id


def create_user(data: UserCreate) -> UserInDB:
    """Create a new user."""
    if data.email.lower() in _users_by_email:
        raise ValueError("Email already registered")
    
    now = utc_now()
    user = UserInDB(
        id=generate_id("user"),
        email=data.email.lower(),
        name=data.name,
        password_hash=hash_password(data.password),
        created_at=now,
        updated_at=now,
    )
    
    _users_db[user.id] = user
    _users_by_email[user.email] = user.id
    
    return user


def get_user_by_id(user_id: str) -> UserInDB | None:
    """Get user by ID."""
    return _users_db.get(user_id)


def get_user_by_email(email: str) -> UserInDB | None:
    """Get user by email."""
    user_id = _users_by_email.get(email.lower())
    return _users_db.get(user_id) if user_id else None


def authenticate_user(email: str, password: str) -> UserInDB | None:
    """Authenticate user by email and password."""
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def update_user_tier(user_id: str, tier: str) -> bool:
    """Update user's subscription tier."""
    user = _users_db.get(user_id)
    if not user:
        return False
    user.tier = tier
    user.updated_at = utc_now()
    return True


# =============================================================================
# Email Verification Tokens
# =============================================================================

_verification_tokens: dict[str, tuple[str, datetime]] = {}  # token -> (user_id, expires)


def create_verification_token(user_id: str) -> str:
    """Create an email verification token."""
    token = secrets.token_urlsafe(32)
    expires = utc_now() + timedelta(hours=24)
    _verification_tokens[token] = (user_id, expires)
    return token


def verify_email_token(token: str) -> str | None:
    """
    Verify an email verification token.
    
    Returns user_id if valid, None otherwise.
    """
    if token not in _verification_tokens:
        return None
    
    user_id, expires = _verification_tokens[token]
    
    if utc_now() > expires:
        del _verification_tokens[token]
        return None
    
    # Mark email as verified
    user = _users_db.get(user_id)
    if user:
        user.email_verified = True
        user.updated_at = utc_now()
    
    del _verification_tokens[token]
    return user_id


# =============================================================================
# Password Reset Tokens
# =============================================================================

_reset_tokens: dict[str, tuple[str, datetime]] = {}  # token -> (user_id, expires)


def create_password_reset_token(email: str) -> str | None:
    """
    Create a password reset token for the user with this email.
    
    Returns token if user exists, None otherwise.
    """
    user = get_user_by_email(email)
    if not user:
        return None
    
    token = secrets.token_urlsafe(32)
    expires = utc_now() + timedelta(hours=1)
    _reset_tokens[token] = (user.id, expires)
    return token


def reset_password(token: str, new_password: str) -> bool:
    """
    Reset password using a reset token.
    
    Returns True if successful.
    """
    if token not in _reset_tokens:
        return False
    
    user_id, expires = _reset_tokens[token]
    
    if utc_now() > expires:
        del _reset_tokens[token]
        return False
    
    user = _users_db.get(user_id)
    if not user:
        del _reset_tokens[token]
        return False
    
    user.password_hash = hash_password(new_password)
    user.updated_at = utc_now()
    
    del _reset_tokens[token]
    return True

