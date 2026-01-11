"""
ADK Configuration Module

Manages configuration for the ADK module including:
- API keys (Gemini, OpenRouter)
- Model selection
- Timeout settings
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class ADKConfig:
    """Configuration for ADK module."""
    enabled: bool
    gemini_api_key: str | None
    openrouter_api_key: str | None
    default_model: str
    current_model: str | None
    timeout_seconds: int
    advanced_model: str
    
    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)
    
    @property
    def has_openrouter(self) -> bool:
        return bool(self.openrouter_api_key)


@lru_cache(maxsize=1)
def get_adk_config() -> ADKConfig:
    """
    Get ADK configuration from environment variables.
    
    Cached for performance - call clear_config_cache() to refresh.
    
    Returns:
        ADKConfig: Configuration object
    """
    # Support both GEMINI_KEY (existing) and GEMINI_API_KEY (ADK standard)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    
    enabled = os.getenv("ADK_ENABLED", "false").lower() == "true"
    enabled = enabled and (bool(gemini_key) or bool(openrouter_key))
    
    # Default model selection
    if gemini_key:
        default_model = "gemini-2.0-flash"
        advanced_model = "gemini-2.0-flash"
    elif openrouter_key:
        default_model = "openrouter/mistralai/devstral-2512:free"
        advanced_model = "openrouter/mistralai/devstral-2512:free"
    else:
        default_model = "gemini-2.0-flash"
        advanced_model = "gemini-2.0-flash"
    
    return ADKConfig(
        enabled=enabled,
        gemini_api_key=gemini_key,
        openrouter_api_key=openrouter_key,
        default_model=default_model,
        current_model=os.getenv("ADK_MODEL"),
        timeout_seconds=int(os.getenv("ADK_TIMEOUT", "120")),
        advanced_model=advanced_model
    )


def clear_config_cache():
    """Clear the configuration cache, forcing a reload on next access."""
    get_adk_config.cache_clear()
