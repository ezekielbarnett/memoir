"""
LLM client configuration using DSPy.

Supports Gemini (primary), OpenAI, and Anthropic.
"""

from __future__ import annotations

import os
from functools import lru_cache

import dspy


@lru_cache
def get_lm(provider: str | None = None, model: str | None = None) -> dspy.LM:
    """
    Get configured language model.
    
    Args:
        provider: 'gemini', 'openai', or 'anthropic'. Defaults to env LLM_PROVIDER.
        model: Model name. Defaults to provider-specific env var.
    
    Returns:
        Configured DSPy LM instance.
    """
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")
    
    if provider == "gemini":
        model = model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        # Accept both GOOGLE_API_KEY and GEMINI_API_KEY
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY not set")
        
        # Use gemini/ prefix for litellm
        return dspy.LM(
            model=f"gemini/{model}",
            api_key=api_key,
        )
    
    elif provider == "openai":
        model = model or os.getenv("OPENAI_MODEL", "gpt-4-turbo")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        return dspy.LM(
            model=f"openai/{model}",
            api_key=api_key,
        )
    
    elif provider == "anthropic":
        model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        return dspy.LM(
            model=f"anthropic/{model}",
            api_key=api_key,
        )
    
    else:
        raise ValueError(f"Unknown provider: {provider}")


def configure_lm(provider: str | None = None, model: str | None = None) -> None:
    """Configure DSPy with the specified LM as default."""
    lm = get_lm(provider, model)
    dspy.configure(lm=lm)

