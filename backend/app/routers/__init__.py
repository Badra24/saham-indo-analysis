"""
ADK API Router

Provides API endpoints for the AI Trading Assistant (ADK module).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """Request model for analyze endpoint."""
    symbol: str
    message: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None


class MessageRequest(BaseModel):
    """Request model for chat message endpoint."""
    message: str
    model: Optional[str] = None


@router.get("/status")
async def get_adk_status():
    """
    Get ADK module status.
    
    Returns ADK configuration status including:
    - Whether ADK is enabled
    - Which API keys are configured
    - Current model selection
    """
    from app.adk import get_adk_status, is_adk_enabled
    from app.adk.runner import get_current_model
    
    status = get_adk_status()
    status["current_model"] = get_current_model() if is_adk_enabled() else None
    
    return status


@router.get("/models")
async def list_models():
    """
    List available AI models.
    
    Returns only models that have the required API keys configured.
    """
    from app.adk import is_adk_enabled
    
    if not is_adk_enabled():
        return {
            "available": [],
            "message": "ADK is not enabled. Set ADK_ENABLED=true and GEMINI_API_KEY in .env"
        }
    
    from app.adk.models import get_available_models, DEFAULT_MODEL
    from app.adk.runner import get_current_model
    
    models = get_available_models()
    
    return {
        "available": models,
        "default": DEFAULT_MODEL,
        "current": get_current_model()
    }


@router.post("/analyze")
async def analyze_stock(request: AnalyzeRequest):
    """
    Run AI analysis on a stock.
    
    Uses the Remora Commander agent to analyze the stock using:
    - Order Flow Analysis (OBI, HAKA/HAKI, Iceberg)
    - Bandarmology (Smart Money detection)
    - Technical Indicators
    - Looping Strategy signals
    
    Args:
        symbol: Stock ticker (e.g., "BBCA")
        message: Optional custom analysis prompt
        model: Optional AI model ID
        session_id: Optional session ID for conversation continuity
    
    Returns:
        AI analysis response with trading recommendations
    """
    from app.adk import is_adk_enabled
    
    if not is_adk_enabled():
        raise HTTPException(
            status_code=503,
            detail="ADK is not enabled. Set ADK_ENABLED=true and GEMINI_API_KEY in .env"
        )
    
    from app.adk.runner import run_agent
    
    # Build analysis message
    if request.message:
        message = request.message
    else:
        message = f"Analisa saham {request.symbol} sekarang dengan lengkap."
    
    result = await run_agent(
        message=message,
        model=request.model,
        session_id=request.session_id
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Analysis failed")
        )
    
    return result


@router.post("/session/{session_id}/message")
async def send_message(session_id: str, request: MessageRequest):
    """
    Send a message to an existing session.
    
    Allows for conversation continuity with the AI agent.
    
    Args:
        session_id: Existing session ID
        message: User message
        model: Optional AI model ID (defaults to session's model)
    
    Returns:
        AI response
    """
    from app.adk import is_adk_enabled
    
    if not is_adk_enabled():
        raise HTTPException(
            status_code=503,
            detail="ADK is not enabled"
        )
    
    from app.adk.runner import run_agent
    
    result = await run_agent(
        message=request.message,
        model=request.model,
        session_id=session_id
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Message failed")
        )
    
    return result


@router.get("/quick/{symbol}")
async def quick_analysis(symbol: str):
    """
    Quick analysis endpoint for a stock.
    
    Provides a fast analysis without custom prompts.
    
    Args:
        symbol: Stock ticker (e.g., "BBCA")
    
    Returns:
        AI analysis response
    """
    from app.adk import is_adk_enabled
    
    if not is_adk_enabled():
        raise HTTPException(
            status_code=503,
            detail="ADK is not enabled"
        )
    
    from app.adk.runner import run_quick_analysis
    
    result = await run_quick_analysis(symbol=symbol)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Analysis failed")
        )
    
    return result


@router.post("/position-size")
async def calculate_position_size(
    symbol: str,
    account_balance: float,
    entry_price: float,
    stop_loss_price: float
):
    """
    Calculate optimal position size using AI.
    
    Uses the Remora methodology (30-30-40 pyramiding) and
    risk management rules (1% risk per trade).
    
    Args:
        symbol: Stock ticker
        account_balance: Total account balance in IDR
        entry_price: Planned entry price
        stop_loss_price: Stop loss level
    
    Returns:
        AI-calculated position sizing recommendation
    """
    from app.adk import is_adk_enabled
    
    if not is_adk_enabled():
        raise HTTPException(
            status_code=503,
            detail="ADK is not enabled"
        )
    
    from app.adk.runner import run_position_sizing
    
    result = await run_position_sizing(
        symbol=symbol,
        account_balance=account_balance,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Calculation failed")
        )
    
    return result


class ChatRequest(BaseModel):
    """Request model for chat endpoint (frontend compatible)."""
    message: str
    session_id: Optional[str] = None
    model: Optional[str] = None


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint for frontend integration.
    
    Compatible with ADKChatPanel component.
    Returns consistent format for frontend handling.
    
    Args:
        message: User message/query
        session_id: Optional session ID for conversation continuity
        model: Optional AI model ID
    
    Returns:
        Dict with success, response, session_id, model
    """
    from app.adk import is_adk_enabled
    
    if not is_adk_enabled():
        return {
            "success": False,
            "error": "not_enabled",
            "message": "ADK is not enabled. Set ADK_ENABLED=true and GEMINI_API_KEY in .env"
        }
    
    from app.adk.runner import run_agent
    
    result = await run_agent(
        message=request.message,
        model=request.model,
        session_id=request.session_id
    )
    
    return result


@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics.
    
    Returns cache entries, their age, and TTL status.
    Useful for monitoring and debugging.
    """
    from app.adk.cache import get_cache
    
    cache = get_cache()
    return cache.stats()


@router.post("/cache/clear")
async def clear_cache():
    """
    Clear all cache entries.
    
    Use when data needs to be refreshed.
    """
    from app.adk.cache import get_cache
    
    cache = get_cache()
    count = cache.clear()
    
    return {
        "success": True,
        "message": f"Cleared {count} cache entries"
    }

