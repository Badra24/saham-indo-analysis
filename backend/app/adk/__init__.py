"""
ADK (Agent Development Kit) Module for Saham-Indo

This module is ISOLATED and can be TOGGLED ON/OFF via config.
If ADK has issues, it will NOT affect other features.

Usage:
    # Check if ADK is enabled
    from app.adk import is_adk_enabled
    if is_adk_enabled():
        from app.adk import get_remora_commander
        agent = get_remora_commander()

Environment Variables:
    ADK_ENABLED=true          # Enable/disable ADK module
    GEMINI_API_KEY=xxx        # Required for Gemini models
    OPENROUTER_API_KEY=xxx    # Optional for OpenRouter models
"""

import os
import logging
from typing import TYPE_CHECKING

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not required if env vars are set externally

# Suppress verbose LiteLLM logging (DEEPSEEK_REASONING_STREAM, etc.)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Filter specific debug messages
class DebugLogFilter(logging.Filter):
    """Filter out noisy debug messages from LiteLLM and related libraries."""
    
    BLOCKED_PATTERNS = [
        "AGENTS_LINK_ESTABLISHED",
        "DEEPSEEK_REASONING_STREAM",
        "Request to litellm",
        "POST Request",
    ]
    
    def filter(self, record):
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            for pattern in self.BLOCKED_PATTERNS:
                if pattern in msg:
                    return False
        return True

# Apply filter to root logger
for handler in logging.root.handlers:
    handler.addFilter(DebugLogFilter())

if TYPE_CHECKING:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner


def is_adk_enabled() -> bool:
    """
    Check if ADK feature is enabled in config.
    
    ADK is enabled only if:
    1. ADK_ENABLED environment variable is set to 'true'
    2. GEMINI_API_KEY OR OPENROUTER_API_KEY is provided
    
    Returns:
        bool: True if ADK is enabled and ready
    """
    try:
        enabled = os.getenv("ADK_ENABLED", "false").lower() == "true"
        # Support both GEMINI_KEY (existing) and GEMINI_API_KEY (ADK standard)
        has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY"))
        has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
        return enabled and (has_gemini or has_openrouter)
    except Exception:
        return False


def get_adk_status() -> dict:
    """
    Get detailed ADK status for debugging.
    
    Returns:
        dict with enabled status and any missing requirements
    """
    enabled_flag = os.getenv("ADK_ENABLED", "false").lower() == "true"
    has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY"))
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    has_any_key = has_gemini or has_openrouter
    
    status = {
        "enabled": enabled_flag and has_any_key,
        "adk_enabled_flag": enabled_flag,
        "gemini_key_set": has_gemini,
        "openrouter_key_set": has_openrouter,
        "missing": []
    }
    
    if not enabled_flag:
        status["missing"].append("ADK_ENABLED=true")
    if not has_any_key:
        status["missing"].append("GEMINI_API_KEY or OPENROUTER_API_KEY")
    
    return status


def get_remora_commander() -> "LlmAgent":
    """
    Get the Remora Commander agent (lazy load).
    
    Returns:
        LlmAgent: The root trading commander agent for IDX
        
    Raises:
        RuntimeError: If ADK is not enabled
    """
    if not is_adk_enabled():
        raise RuntimeError(
            "ADK is not enabled. Set ADK_ENABLED=true and GEMINI_API_KEY in .env"
        )
    from app.adk.agents.remora_commander import remora_commander
    return remora_commander


def get_runner() -> "InMemoryRunner":
    """
    Get the ADK runner (lazy load).
    
    Returns:
        InMemoryRunner: Runner for agent execution
        
    Raises:
        RuntimeError: If ADK is not enabled
    """
    if not is_adk_enabled():
        raise RuntimeError("ADK is not enabled")
    from app.adk.runner import create_runner
    return create_runner()


__all__ = [
    "is_adk_enabled",
    "get_adk_status",
    "get_remora_commander", 
    "get_runner"
]
