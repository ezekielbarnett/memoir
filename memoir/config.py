"""
Application configuration.

Loads settings from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    # ==========================================================================
    # Environment
    # ==========================================================================
    
    environment: str = "development"
    debug: bool = True
    
    # ==========================================================================
    # API Server
    # ==========================================================================
    
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    secret_key: str = "dev-secret-change-in-production"
    
    # ==========================================================================
    # AI / LLM
    # ==========================================================================
    
    # Primary: Gemini (accepts either GOOGLE_API_KEY or GEMINI_API_KEY)
    google_api_key: str = ""
    gemini_api_key: str = ""  # Alias for google_api_key
    gemini_model: str = "gemini-2.0-flash"
    
    # Fallback providers
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-opus-20240229"
    
    # Which provider to use
    llm_provider: str = "gemini"
    
    # ==========================================================================
    # AWS
    # ==========================================================================
    
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket: str = "memoir-content"
    aws_dynamodb_table_prefix: str = "memoir_"
    aws_ses_from_email: str = ""
    
    # ==========================================================================
    # Database
    # ==========================================================================
    
    database_url: str = ""
    
    # ==========================================================================
    # Authentication
    # ==========================================================================
    
    jwt_secret_key: str = "dev-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    
    # OAuth providers (optional)
    # See DEPLOY.md for setup instructions
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    facebook_oauth_client_id: str = ""
    facebook_oauth_client_secret: str = ""
    apple_oauth_client_id: str = ""
    apple_oauth_team_id: str = ""
    apple_oauth_key_id: str = ""
    
    # ==========================================================================
    # Optional Services
    # ==========================================================================
    
    redis_url: str = ""
    sentry_dsn: str = ""
    
    # ==========================================================================
    # Helpers
    # ==========================================================================
    
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def use_aws(self) -> bool:
        """Whether AWS services should be used."""
        return bool(self.aws_access_key_id and self.aws_secret_access_key)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

