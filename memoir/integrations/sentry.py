# =============================================================================
# Sentry Error Tracking Integration
# =============================================================================
#
# Setup:
#   1. Create account at sentry.io
#   2. Create a Python project
#   3. Copy DSN to .env: SENTRY_DSN=https://...@sentry.io/...
#
# Usage:
#   Call init_sentry() at app startup (in memoir/api/app.py)
#
# =============================================================================

import logging
from functools import wraps
from typing import Any, Callable

from memoir.config import get_settings

logger = logging.getLogger(__name__)

# Sentry SDK is optional - gracefully degrade if not installed
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    sentry_sdk = None


def init_sentry() -> bool:
    """
    Initialize Sentry error tracking.
    
    Returns True if initialized, False if skipped.
    """
    if not SENTRY_AVAILABLE:
        logger.info("Sentry SDK not installed - error tracking disabled")
        return False
    
    settings = get_settings()
    
    if not settings.sentry_dsn:
        logger.info("SENTRY_DSN not set - error tracking disabled")
        return False
    
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        
        # Performance monitoring (sample 10% of transactions in prod)
        traces_sample_rate=0.1 if settings.environment == "production" else 1.0,
        
        # Profile 10% of sampled transactions
        profiles_sample_rate=0.1,
        
        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        
        # Don't send PII by default
        send_default_pii=False,
        
        # Filter out health checks
        before_send=_filter_events,
        before_send_transaction=_filter_transactions,
    )
    
    logger.info(f"Sentry initialized for {settings.environment}")
    return True


def _filter_events(event: dict, hint: dict) -> dict | None:
    """Filter out noisy or sensitive events."""
    # Skip expected errors
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]
        
        # Don't report 404s, auth failures, validation errors
        from fastapi import HTTPException
        if isinstance(exc_value, HTTPException):
            if exc_value.status_code in (401, 403, 404, 422):
                return None
    
    # Scrub sensitive data from request
    if "request" in event:
        request = event["request"]
        if "headers" in request:
            # Remove auth headers
            headers = request["headers"]
            for key in list(headers.keys()):
                if key.lower() in ("authorization", "cookie", "x-api-key"):
                    headers[key] = "[Filtered]"
    
    return event


def _filter_transactions(event: dict, hint: dict) -> dict | None:
    """Filter out noisy transactions."""
    transaction = event.get("transaction", "")
    
    # Skip health checks and static files
    if transaction in ("/health", "/healthz", "/ready", "/metrics"):
        return None
    if transaction.startswith("/static"):
        return None
    
    return event


def capture_exception(error: Exception, **context) -> str | None:
    """
    Capture an exception to Sentry.
    
    Returns the event ID if captured, None otherwise.
    """
    if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
        logger.exception("Error (Sentry disabled)", exc_info=error)
        return None
    
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        return sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", **context) -> str | None:
    """
    Capture a message to Sentry.
    
    Levels: fatal, error, warning, info, debug
    """
    if not SENTRY_AVAILABLE or not sentry_sdk.Hub.current.client:
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
        return None
    
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        return sentry_sdk.capture_message(message, level=level)


def set_user(user_id: str, email: str | None = None, **extra) -> None:
    """Set the current user context for error reports."""
    if SENTRY_AVAILABLE and sentry_sdk.Hub.current.client:
        sentry_sdk.set_user({
            "id": user_id,
            "email": email,
            **extra,
        })


def set_context(name: str, data: dict) -> None:
    """Add custom context to error reports."""
    if SENTRY_AVAILABLE and sentry_sdk.Hub.current.client:
        sentry_sdk.set_context(name, data)


def set_tag(key: str, value: str) -> None:
    """Add a tag for filtering in Sentry."""
    if SENTRY_AVAILABLE and sentry_sdk.Hub.current.client:
        sentry_sdk.set_tag(key, value)


def track_performance(name: str):
    """
    Decorator to track function performance in Sentry.
    
    Usage:
        @track_performance("generate_section")
        async def generate_section(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        if not SENTRY_AVAILABLE:
            return func
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with sentry_sdk.start_transaction(op="function", name=name):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with sentry_sdk.start_transaction(op="function", name=name):
                return func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

