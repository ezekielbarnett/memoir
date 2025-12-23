# =============================================================================
# OAuth Integration (Google, Facebook, Apple)
# =============================================================================
#
# Setup (Google):
#   1. Go to https://console.cloud.google.com/apis/credentials
#   2. Create OAuth 2.0 Client ID (Web application)
#   3. Add authorized redirect URI: https://yourdomain.com/auth/google/callback
#   4. Set env vars:
#      - GOOGLE_OAUTH_CLIENT_ID=...
#      - GOOGLE_OAUTH_CLIENT_SECRET=...
#
# Setup (Facebook):
#   1. Go to https://developers.facebook.com/apps
#   2. Create app, add Facebook Login product
#   3. Set env vars:
#      - FACEBOOK_OAUTH_CLIENT_ID=...
#      - FACEBOOK_OAUTH_CLIENT_SECRET=...
#
# Setup (Apple):
#   1. Requires Apple Developer account ($99/yr)
#   2. Create Service ID in Apple Developer portal
#   3. Set env vars:
#      - APPLE_OAUTH_CLIENT_ID=...
#      - APPLE_OAUTH_TEAM_ID=...
#      - APPLE_OAUTH_KEY_ID=...
#      - APPLE_OAUTH_PRIVATE_KEY=... (or path to .p8 file)
#
# =============================================================================

import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from memoir.config import get_settings
from memoir.core.utils import generate_id

logger = logging.getLogger(__name__)


# =============================================================================
# Models
# =============================================================================

class OAuthUserInfo(BaseModel):
    """User info retrieved from OAuth provider."""
    provider: str  # "google", "facebook", "apple"
    provider_user_id: str
    email: str
    name: str
    picture_url: str | None = None
    email_verified: bool = True


class OAuthError(Exception):
    """OAuth flow error."""
    pass


# =============================================================================
# Google OAuth
# =============================================================================

class GoogleOAuth:
    """Google OAuth 2.0 implementation."""
    
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    def __init__(self):
        self.settings = get_settings()
    
    @property
    def is_configured(self) -> bool:
        """Check if Google OAuth is configured."""
        return bool(
            self.settings.google_oauth_client_id
            and self.settings.google_oauth_client_secret
        )
    
    @property
    def redirect_uri(self) -> str:
        """Get the callback URL."""
        # Use first CORS origin as base URL
        base = self.settings.cors_origins_list[0] if self.settings.cors_origins_list else "http://localhost:3000"
        return f"{base}/auth/google/callback"
    
    def get_authorize_url(self, state: str | None = None) -> str:
        """
        Get URL to redirect user to for Google sign-in.
        
        Args:
            state: Optional state parameter for CSRF protection
        
        Returns:
            URL to redirect user to
        """
        if not self.is_configured:
            raise OAuthError("Google OAuth not configured")
        
        params = {
            "client_id": self.settings.google_oauth_client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account",
        }
        if state:
            params["state"] = state
        
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str) -> dict[str, Any]:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from callback
        
        Returns:
            Token response with access_token, refresh_token, id_token
        """
        if not self.is_configured:
            raise OAuthError("Google OAuth not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.settings.google_oauth_client_id,
                    "client_secret": self.settings.google_oauth_client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            
            if response.status_code != 200:
                logger.error(f"Google token exchange failed: {response.text}")
                raise OAuthError(f"Token exchange failed: {response.status_code}")
            
            return response.json()
    
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Get user info from Google.
        
        Args:
            access_token: Access token from token exchange
        
        Returns:
            User info from Google
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                logger.error(f"Google userinfo failed: {response.text}")
                raise OAuthError(f"Failed to get user info: {response.status_code}")
            
            data = response.json()
            
            return OAuthUserInfo(
                provider="google",
                provider_user_id=data["id"],
                email=data["email"],
                name=data.get("name", data.get("email", "").split("@")[0]),
                picture_url=data.get("picture"),
                email_verified=data.get("verified_email", True),
            )
    
    async def authenticate(self, code: str) -> OAuthUserInfo:
        """
        Complete OAuth flow: exchange code and get user info.
        
        Args:
            code: Authorization code from callback
        
        Returns:
            User info from Google
        """
        tokens = await self.exchange_code(code)
        return await self.get_user_info(tokens["access_token"])


# =============================================================================
# Facebook OAuth
# =============================================================================

class FacebookOAuth:
    """Facebook OAuth 2.0 implementation."""
    
    AUTHORIZE_URL = "https://www.facebook.com/v18.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
    USERINFO_URL = "https://graph.facebook.com/v18.0/me"
    
    def __init__(self):
        self.settings = get_settings()
    
    @property
    def is_configured(self) -> bool:
        """Check if Facebook OAuth is configured."""
        return bool(
            getattr(self.settings, 'facebook_oauth_client_id', None)
            and getattr(self.settings, 'facebook_oauth_client_secret', None)
        )
    
    @property
    def redirect_uri(self) -> str:
        base = self.settings.cors_origins_list[0] if self.settings.cors_origins_list else "http://localhost:3000"
        return f"{base}/auth/facebook/callback"
    
    def get_authorize_url(self, state: str | None = None) -> str:
        if not self.is_configured:
            raise OAuthError("Facebook OAuth not configured")
        
        params = {
            "client_id": self.settings.facebook_oauth_client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "email,public_profile",
        }
        if state:
            params["state"] = state
        
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str) -> dict[str, Any]:
        if not self.is_configured:
            raise OAuthError("Facebook OAuth not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.TOKEN_URL,
                params={
                    "client_id": self.settings.facebook_oauth_client_id,
                    "client_secret": self.settings.facebook_oauth_client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )
            
            if response.status_code != 200:
                raise OAuthError(f"Token exchange failed: {response.status_code}")
            
            return response.json()
    
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                params={
                    "fields": "id,email,name,picture.type(large)",
                    "access_token": access_token,
                },
            )
            
            if response.status_code != 200:
                raise OAuthError(f"Failed to get user info: {response.status_code}")
            
            data = response.json()
            
            return OAuthUserInfo(
                provider="facebook",
                provider_user_id=data["id"],
                email=data.get("email", ""),
                name=data.get("name", ""),
                picture_url=data.get("picture", {}).get("data", {}).get("url"),
                email_verified=True,  # Facebook emails are verified
            )
    
    async def authenticate(self, code: str) -> OAuthUserInfo:
        tokens = await self.exchange_code(code)
        return await self.get_user_info(tokens["access_token"])


# =============================================================================
# OAuth Manager
# =============================================================================

class OAuthManager:
    """Manage all OAuth providers."""
    
    def __init__(self):
        self.google = GoogleOAuth()
        self.facebook = FacebookOAuth()
        # Apple OAuth is more complex - add when needed
        
        # State tokens for CSRF protection (in production, use Redis)
        self._pending_states: dict[str, str] = {}  # state -> provider
    
    def get_available_providers(self) -> list[str]:
        """Get list of configured OAuth providers."""
        providers = []
        if self.google.is_configured:
            providers.append("google")
        if self.facebook.is_configured:
            providers.append("facebook")
        return providers
    
    def create_state(self, provider: str) -> str:
        """Create a state token for CSRF protection."""
        state = generate_id("oauth")
        self._pending_states[state] = provider
        return state
    
    def validate_state(self, state: str) -> str | None:
        """Validate and consume a state token. Returns provider if valid."""
        return self._pending_states.pop(state, None)
    
    def get_authorize_url(self, provider: str) -> str:
        """Get authorization URL for a provider."""
        state = self.create_state(provider)
        
        if provider == "google":
            return self.google.get_authorize_url(state)
        elif provider == "facebook":
            return self.facebook.get_authorize_url(state)
        else:
            raise OAuthError(f"Unknown provider: {provider}")
    
    async def authenticate(self, provider: str, code: str) -> OAuthUserInfo:
        """Complete authentication for a provider."""
        if provider == "google":
            return await self.google.authenticate(code)
        elif provider == "facebook":
            return await self.facebook.authenticate(code)
        else:
            raise OAuthError(f"Unknown provider: {provider}")


# Global instance
_oauth_manager: OAuthManager | None = None


def get_oauth_manager() -> OAuthManager:
    """Get the OAuth manager singleton."""
    global _oauth_manager
    if _oauth_manager is None:
        _oauth_manager = OAuthManager()
    return _oauth_manager

