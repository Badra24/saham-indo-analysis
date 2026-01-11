"""
ADK Runner - Safe execution wrapper for agents

Provides isolated execution with error handling, timeouts,
and graceful degradation when ADK has issues.

Supports dynamic model selection for multi-model support.
"""

import asyncio
import uuid
from typing import Optional, Dict, Any
import os

from app.adk.config import get_adk_config
from app.adk.exceptions import (
    ADKNotEnabledError,
    ADKTimeoutError,
    ADKAgentError,
)


# Global runner instance (single runner, model can be changed)
_runner_instance = None
_current_model: Optional[str] = None


def _update_agent_model(model_id: str):
    """
    Update ALL agents' models.
    
    Args:
        model_id: Model identifier from available models
    """
    from app.adk.models import get_model_for_agent, DEFAULT_MODEL
    from app.adk.agents.remora_commander import remora_commander
    
    # Get the model object (string or LiteLlm wrapper)
    model = get_model_for_agent(model_id or DEFAULT_MODEL)
    
    # Update model on main agent
    remora_commander.model = model


def get_runner(model_id: Optional[str] = None):
    """
    Get or create the InMemoryRunner instance.
    
    If a different model is requested, updates the agent's model.
    
    Args:
        model_id: Optional model identifier. Uses default if not specified.
    
    Returns:
        InMemoryRunner: Runner for agent execution
        
    Raises:
        ADKNotEnabledError: If ADK is not enabled
    """
    global _runner_instance, _current_model
    
    config = get_adk_config()
    if not config.enabled:
        raise ADKNotEnabledError("ADK is not enabled")
    
    from app.adk.models import DEFAULT_MODEL
    selected_model = model_id or config.current_model or DEFAULT_MODEL
    
    # Check if we have required keys
    if selected_model.startswith("gemini") and not config.has_gemini:
        raise ADKNotEnabledError("GEMINI_API_KEY is not set")
    
    if selected_model.startswith("openrouter") and not config.has_openrouter:
        raise ADKNotEnabledError("OPENROUTER_API_KEY is not set")
    
    # Set API keys in environment for google.adk
    if config.gemini_api_key:
        os.environ["GOOGLE_API_KEY"] = config.gemini_api_key
    if config.openrouter_api_key:
        os.environ["OPENROUTER_API_KEY"] = config.openrouter_api_key
    
    # Create runner if not exists
    if _runner_instance is None:
        from google.adk.runners import InMemoryRunner
        from app.adk.agents.remora_commander import remora_commander
        
        # Set initial model
        _update_agent_model(selected_model)
        
        # Create runner with the remora commander
        _runner_instance = InMemoryRunner(agent=remora_commander)
        _current_model = selected_model
    
    # If model changed, recreate runner
    elif selected_model != _current_model:
        from google.adk.runners import InMemoryRunner
        from app.adk.agents.remora_commander import remora_commander
        
        _update_agent_model(selected_model)
        _runner_instance = InMemoryRunner(agent=remora_commander)
        _current_model = selected_model
    
    return _runner_instance


def get_current_model() -> str:
    """Get the currently active model ID."""
    global _current_model
    if _current_model:
        return _current_model
    from app.adk.models import DEFAULT_MODEL
    return DEFAULT_MODEL


def reset_runner():
    """Reset the runner instance."""
    global _runner_instance, _current_model
    _runner_instance = None
    _current_model = None


async def ensure_session(runner, user_id: str, session_id: str) -> None:
    """Ensure a session exists, create if not."""
    existing = await runner.session_service.get_session(
        app_name=runner.app_name,
        user_id=user_id,
        session_id=session_id
    )
    
    if existing is None:
        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id
        )


async def run_agent(
    message: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    timeout: Optional[int] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the Remora Commander agent with a message.
    
    This is the main entry point for agent execution.
    
    Args:
        message: User message/query to send to the agent
        session_id: Optional session ID for context persistence
        user_id: Optional user ID (defaults to 'default_user')
        timeout: Optional timeout in seconds
        model: Optional model ID to use
    
    Returns:
        Dict with success, response, session_id, model
    """
    config = get_adk_config()
    
    if not config.enabled:
        return {
            "success": False,
            "error": "not_enabled",
            "message": "ADK is not enabled. Set ADK_ENABLED=true and GEMINI_API_KEY in .env"
        }
    
    from app.adk.models import DEFAULT_MODEL, validate_model
    selected_model = model or config.current_model or DEFAULT_MODEL
    
    # Validate model
    is_valid, error_msg = validate_model(selected_model)
    if not is_valid:
        return {
            "success": False,
            "error": "invalid_model",
            "message": error_msg
        }
    
    # Generate IDs if not provided
    actual_session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"
    actual_user_id = user_id or "default_user"
    
    try:
        from google.genai import types
        
        runner = get_runner(model_id=selected_model)
        timeout_seconds = timeout or config.timeout_seconds
        
        await ensure_session(runner, actual_user_id, actual_session_id)
        
        content = types.Content(
            role="user",
            parts=[types.Part(text=message)]
        )
        
        async def execute_agent():
            response_parts = []
            
            try:
                async for event in runner.run_async(
                    user_id=actual_user_id,
                    session_id=actual_session_id,
                    new_message=content
                ):
                    if hasattr(event, 'content') and event.content:
                        if hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    response_parts.append(part.text)
                        elif hasattr(event.content, 'text'):
                            response_parts.append(event.content.text)
                        elif isinstance(event.content, str):
                            response_parts.append(event.content)
                    elif hasattr(event, 'text') and event.text:
                        response_parts.append(event.text)
                        
            except (TypeError, AttributeError) as e:
                # Fallback for non-streaming
                print(f"Streaming not supported ({str(e)}), attempting sync...")
                try:
                    response = await runner.run(
                        user_id=actual_user_id,
                        session_id=actual_session_id,
                        new_message=content
                    )
                    if hasattr(response, 'text'):
                        return response.text
                    elif isinstance(response, str):
                        return response
                    return str(response)
                except Exception as sync_error:
                    raise sync_error
            
            return "".join(response_parts) if response_parts else "No response generated"
        
        response_text = await asyncio.wait_for(
            execute_agent(),
            timeout=timeout_seconds
        )
        
        return {
            "success": True,
            "response": response_text,
            "session_id": actual_session_id,
            "user_id": actual_user_id,
            "model": selected_model
        }
        
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "timeout",
            "message": f"Agent did not respond within {timeout_seconds} seconds.",
            "session_id": actual_session_id
        }
    except ADKNotEnabledError as e:
        return {
            "success": False,
            "error": "not_enabled",
            "message": str(e)
        }
    except ImportError as e:
        return {
            "success": False,
            "error": "import_error",
            "message": f"Failed to load ADK dependencies: {str(e)}. Run: pip install google-adk"
        }
    except Exception as e:
        error_message = str(e)
        error_type = type(e).__name__
        
        if "429" in error_message or "RESOURCE_EXHAUSTED" in error_message:
            return {
                "success": False,
                "error": "rate_limit",
                "message": "AI rate limit exceeded. Please wait and try again.",
                "type": error_type,
                "session_id": actual_session_id
            }
        
        return {
            "success": False,
            "error": "agent_error",
            "message": error_message,
            "type": error_type,
            "session_id": actual_session_id if 'actual_session_id' in locals() else None
        }


async def run_quick_analysis(symbol: str = "BBCA") -> Dict[str, Any]:
    """Run a quick analysis for a stock symbol."""
    message = f"""Analisa saham {symbol} sekarang. Berikan:
1. Order Flow Analysis (OBI, HAKA/HAKI, Iceberg detection)
2. Bandarmology & Smart Money detection
3. Technical Indicators (RSI, MACD, VWAP, EMA)
4. Looping Strategy signal dan rekomendasi"""
    
    return await run_agent(message)


async def run_position_sizing(
    symbol: str,
    account_balance: float,
    entry_price: float,
    stop_loss_price: float
) -> Dict[str, Any]:
    """Run position sizing calculation."""
    message = f"""Hitung position size untuk saham {symbol}:
- Account Balance: Rp {account_balance:,.0f}
- Entry Price: Rp {entry_price:,.0f}  
- Stop Loss: Rp {stop_loss_price:,.0f}

Berikan position size yang aman dengan aturan 1% risk dan piramida 30-30-40."""
    
    return await run_agent(message)
