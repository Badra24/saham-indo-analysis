"""
ADK Models Module - Multi-Model Support

This module provides model management and LiteLLM integration
for using multiple AI providers (Gemini, OpenRouter, etc).

Usage:
    from app.adk.models import get_available_models, get_model_for_agent
    
    models = get_available_models()
    model = get_model_for_agent("gemini-2.0-flash")
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union
import os


@dataclass
class ModelConfig:
    """Configuration for an AI model."""
    id: str                    # Unique identifier
    name: str                  # Display name
    provider: str              # Provider name (gemini, openrouter)
    model_string: str          # Model string for API call
    description: str           # Short description
    rate_limit: str            # Approximate rate limit info
    is_free: bool = False      # Whether it's free tier
    requires_key: str = ""     # Required API key env var


# Available models configuration
AVAILABLE_MODELS: Dict[str, ModelConfig] = {
    # Gemini Models (Native)
    # "gemini-2.0-flash": ModelConfig(
    #     id="gemini-2.0-flash",
    #     name="Gemini 2.0 Flash",
    #     provider="gemini",
    #     model_string="gemini-2.0-flash",
    #     description="Google's fastest Gemini model - great for quick analysis",
    #     rate_limit="15 RPM (free tier)",
    #     is_free=True,
    #     requires_key="GEMINI_API_KEY"
    # ),
    
    # "gemini-1.5-pro": ModelConfig(
    #     id="gemini-1.5-pro",
    #     name="Gemini 1.5 Pro",
    #     provider="gemini",
    #     model_string="gemini-1.5-pro",
    #     description="Google's advanced Gemini model - better reasoning",
    #     rate_limit="2 RPM (free tier)",
    #     is_free=True,
    #     requires_key="GEMINI_API_KEY"
    # ),
    
    # OpenRouter Free Models
    "openrouter/xiaomi/mimo-v2-flash:free": ModelConfig(
        id="openrouter/xiaomi/mimo-v2-flash:free",
        name="Xiaomi MIMO v2 Flash",
        provider="openrouter",
        model_string="openrouter/xiaomi/mimo-v2-flash:free",
        description="Xiaomi's fast multimodal model - free tier",
        rate_limit="Free",
        is_free=True,
        requires_key="OPENROUTER_API_KEY"
    ),
    
    "openrouter/mistralai/devstral-2512:free": ModelConfig(
        id="openrouter/mistralai/devstral-2512:free",
        name="Mistral Devstral 2512 (FREE)",
        provider="openrouter",
        model_string="openrouter/mistralai/devstral-2512:free",
        description="Mistral's developer model - code & reasoning",
        rate_limit="Free",
        is_free=True,
        requires_key="OPENROUTER_API_KEY"
    ),
    
    # "openrouter/google/gemini-2.0-flash-exp:free": ModelConfig(
    #     id="openrouter/google/gemini-2.0-flash-exp:free",
    #     name="Gemini 2.0 Flash Exp (FREE via OpenRouter)",
    #     provider="openrouter",
    #     model_string="openrouter/google/gemini-2.0-flash-exp:free",
    #     description="Gemini Flash via OpenRouter - no API key needed",
    #     rate_limit="Free",
    #     is_free=True,
    #     requires_key="OPENROUTER_API_KEY"
    # ),
}

# Default model
DEFAULT_MODEL = "openrouter/mistralai/devstral-2512:free"


def get_available_models() -> list[dict]:
    """
    Get list of available models with their configurations.
    
    Only returns models where the required API key is set.
    
    Returns:
        List of model info dictionaries
    """
    available = []
    
    # Check for both GEMINI_KEY and GEMINI_API_KEY
    gemini_available = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY"))
    
    for model_id, config in AVAILABLE_MODELS.items():
        # Check if required API key is available
        if config.requires_key == "GEMINI_API_KEY" and not gemini_available:
            continue
        if config.requires_key == "OPENROUTER_API_KEY" and not os.getenv("OPENROUTER_API_KEY"):
            continue
            
        available.append({
            "id": config.id,
            "name": config.name,
            "provider": config.provider,
            "description": config.description,
            "rate_limit": config.rate_limit,
            "is_free": config.is_free
        })
    
    return available


def get_model_config(model_id: str) -> Optional[ModelConfig]:
    """
    Get model configuration by ID.
    
    Args:
        model_id: Model identifier
        
    Returns:
        ModelConfig or None if not found
    """
    return AVAILABLE_MODELS.get(model_id)


def get_model_for_agent(model_id: str) -> Union[str, Any]:
    """
    Get the model object/string for use with LlmAgent.
    
    For Gemini models, returns the model string directly.
    For OpenRouter/LiteLLM models, returns a LiteLlm wrapper.
    
    Args:
        model_id: Model identifier from AVAILABLE_MODELS
        
    Returns:
        Model string or LiteLlm wrapper object
        
    Raises:
        ValueError: If model is not available or API key missing
    """
    config = AVAILABLE_MODELS.get(model_id)
    
    if not config:
        raise ValueError(f"Unknown model: {model_id}")
    
    # Check for Gemini key availability (support both env var names)
    gemini_available = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY"))
    
    # Check required API key
    if config.requires_key == "GEMINI_API_KEY" and not gemini_available:
        raise ValueError(f"Missing required API key: GEMINI_API_KEY or GEMINI_KEY")
    if config.requires_key == "OPENROUTER_API_KEY" and not os.getenv(config.requires_key):
        raise ValueError(f"Missing required API key: {config.requires_key}")
    
    # For native Gemini models, just return the string
    if config.provider == "gemini":
        return config.model_string
    
    # For OpenRouter/other providers, use LiteLLM wrapper
    if config.provider == "openrouter":
        try:
            from google.adk.models.lite_llm import LiteLlm
            
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if openrouter_key:
                os.environ["OPENROUTER_API_KEY"] = openrouter_key
            
            return LiteLlm(
                model=config.model_string,
                stream=False,  # Disable streaming for tool compatibility
                temperature=0.7,
                max_tokens=8192,
                extra_headers={
                    "X-Title": "Saham-Indo AI",
                    "HTTP-Referer": "https://saham-indo.local"
                }
            )
        except ImportError:
            raise ValueError("LiteLLM not installed. Run: pip install litellm")
    
    return config.model_string


def validate_model(model_id: str) -> tuple[bool, str]:
    """
    Validate if a model can be used.
    
    Args:
        model_id: Model identifier
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    config = AVAILABLE_MODELS.get(model_id)
    
    if not config:
        return False, f"Unknown model: {model_id}"
    
    # Check for Gemini key availability (support both env var names)
    gemini_available = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY"))
    
    if config.requires_key == "GEMINI_API_KEY" and not gemini_available:
        return False, "Missing API key: GEMINI_API_KEY or GEMINI_KEY"
    if config.requires_key == "OPENROUTER_API_KEY" and not os.getenv(config.requires_key):
        return False, f"Missing API key: {config.requires_key}"
    
    return True, ""
