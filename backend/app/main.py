"""
Saham-Indo API - Indonesian Stock Trading Platform

Features:
- Market Data & Technical Indicators
- Order Flow Analysis (OBI, HAKA/HAKI, Iceberg)
- Bandarmology (Smart Money Detection)
- Looping Strategy Trading Signals
- Risk Management (Kill Switch, Position Sizing)
- AI Trading Assistant (ADK Module - Optional)
"""
# Load .env file FIRST before any other imports that use settings
from dotenv import load_dotenv
load_dotenv()  # Explicitly load .env to ensure pydantic-settings can access it

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from collections import defaultdict
import time
from app.api.endpoints import router as api_router

# ============================================================================
# ADK MODULE - CONDITIONAL LOADING
# ============================================================================
# ADK is loaded only if enabled and configured.
# If ADK has issues, the rest of the application continues to work normally.

ADK_AVAILABLE = False
try:
    from app.adk import is_adk_enabled
    if is_adk_enabled():
        ADK_AVAILABLE = True
except ImportError:
    pass  # ADK dependencies not installed
except Exception as e:
    print(f"⚠️ ADK module error (non-fatal): {e}")


# ============================================================================
# RATE LIMITING MIDDLEWARE (Like crypto-trades)
# ============================================================================

class RateLimitMiddleware:
    """
    Simple rate limiting middleware.
    Limits requests per IP address per minute.
    """
    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
    
    def is_rate_limited(self, client_ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip] 
            if ts > minute_ago
        ]
        
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return True
        
        self.requests[client_ip].append(now)
        return False
    
    def get_remaining(self, client_ip: str) -> int:
        now = time.time()
        minute_ago = now - 60
        recent = [ts for ts in self.requests.get(client_ip, []) if ts > minute_ago]
        return max(0, self.requests_per_minute - len(recent))


rate_limiter = RateLimitMiddleware(requests_per_minute=120)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    print("🚀 Starting Saham-Indo Trading Platform...")
    print(f"   Rate Limit: 120 requests/minute per IP")
    print(f"   ADK Module: {'✓ Enabled (AI Trading Assistant)' if ADK_AVAILABLE else '✗ Disabled'}")
    print(f"   ADK Module: {'✓ Enabled (AI Trading Assistant)' if ADK_AVAILABLE else '✗ Disabled'}")
    yield
    print("👋 Shutting down...")
    
    # Close DB connection cleanly
    try:
        from app.services.database_service import db_service
        db_service.close()
    except Exception as e:
        print(f"⚠️ Error closing DB on shutdown: {e}")


app = FastAPI(
    title="Saham-Indo AI Trading Platform",
    description="""
    Platform trading saham Indonesia dengan analisa algorithmic tingkat institusi.
    
    ## Features
    - **Market Data**: OHLCV, ticker info, historical prices
    - **Technical Indicators**: RSI, MACD-V, VWAP, EMA, Bollinger Bands
    - **Order Flow Analysis**: OBI, HAKA/HAKI, Iceberg Detection
    - **Bandarmology**: Smart Money detection menggunakan analisa intensi
    - **Looping Strategy**: Trading signals with 30-30-40 pyramiding
    - **Risk Management**: Kill switch, ATR-based position sizing
    - **AI Assistant**: Remora-Quant AI analysis (optional)
    
    ## Rate Limits
    - 120 requests per minute per IP address
    """,
    version="1.1.0",
    lifespan=lifespan
)


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limit incoming requests by IP"""
    client_ip = request.client.host if request.client else "unknown"
    
    # Skip rate limiting for health checks
    if request.url.path in ["/", "/api/health"]:
        return await call_next(request)
    
    if rate_limiter.is_rate_limited(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": "Too many requests. Please slow down.",
                "limit": "120 requests per minute"
            }
        )
    
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = "120"
    response.headers["X-RateLimit-Remaining"] = str(rate_limiter.get_remaining(client_ip))
    
    return response


# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include main API router
app.include_router(api_router, prefix="/api/v1")

# Analytics Router (Deep Analysis)
from app.routers import analytics
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])

# Ingest Router (CSV Upload)
from app.routers import ingest
app.include_router(ingest.router, prefix="/api/v1", tags=["Data Ingestion"])

# ADK Router - Conditional registration
if ADK_AVAILABLE:
    from app.routers import router as adk_router
    app.include_router(adk_router, prefix="/api/adk", tags=["AI Trading Assistant"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": "Saham-Indo Trading Platform",
        "version": "1.0.0",
        "adk_enabled": ADK_AVAILABLE
    }


@app.get("/api/health")
async def health_check():
    """
    Comprehensive API health check.
    
    Returns system status and ADK module status.
    """
    from datetime import datetime
    
    adk_status = None
    if ADK_AVAILABLE:
        try:
            from app.adk import get_adk_status
            adk_status = get_adk_status()
        except Exception:
            adk_status = {"error": "Could not retrieve ADK status"}
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "adk": {
            "enabled": ADK_AVAILABLE,
            "status": adk_status
        }
    }


# ============================================================================
# STOCKBIT TOKEN MANAGEMENT (For Docker Hot-Reload)
# ============================================================================
import os
from fastapi import Header, HTTPException
from pydantic import BaseModel

# Rate limiter for sensitive endpoints
_token_attempt_count = {}
_token_attempt_limit = 5  # Max 5 attempts per minute

def _check_admin_auth(admin_key: str = None) -> bool:
    """Verify admin secret key."""
    expected_key = os.getenv("ADMIN_SECRET_KEY", "")
    
    if not expected_key or expected_key == "change_this_to_a_random_secret_key":
        # If no key configured, allow access (dev mode)
        return True
    
    return admin_key == expected_key

def _rate_limit_check(client_id: str) -> bool:
    """Check if client has exceeded rate limit for token operations."""
    import time
    now = time.time()
    minute_ago = now - 60
    
    # Clean old attempts
    if client_id in _token_attempt_count:
        _token_attempt_count[client_id] = [
            ts for ts in _token_attempt_count[client_id] if ts > minute_ago
        ]
    else:
        _token_attempt_count[client_id] = []
    
    if len(_token_attempt_count[client_id]) >= _token_attempt_limit:
        return False
    
    _token_attempt_count[client_id].append(now)
    return True


@app.get("/api/stockbit/status")
async def stockbit_status():
    """
    Check Stockbit client status (public endpoint).
    
    Returns:
        - token_valid: Whether current token is working
        - needs_refresh: True if token expired (401 received)
        - last_error: Last error message if any
        - request_count: Total requests made
    """
    try:
        from app.services.stockbit_client import stockbit_client
        status = stockbit_client.get_status()
        
        # Hide sensitive details in public response
        return {
            "success": True,
            "token_valid": status.get("token_valid"),
            "token_set": status.get("token_set"),
            "needs_refresh": status.get("needs_refresh"),
            "request_count": status.get("request_count"),
            # Only show error message, not full details
            "has_error": status.get("last_error") is not None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


class TokenUpdateRequest(BaseModel):
    token: str


@app.post("/api/stockbit/token")
async def update_stockbit_token(
    request: Request,
    body: TokenUpdateRequest,
    x_admin_key: str = Header(None, alias="X-Admin-Key")
):
    """
    Update Stockbit token at runtime (PROTECTED - requires admin key).
    
    Headers:
        X-Admin-Key: Your ADMIN_SECRET_KEY from .env
    
    Body:
        {"token": "new_stockbit_token_here"}
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limit check
    if not _rate_limit_check(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many token update attempts. Please wait a minute."
        )
    
    # Auth check
    if not _check_admin_auth(x_admin_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Admin-Key header"
        )
    
    try:
        from app.services.stockbit_client import stockbit_client
        
        if not body.token:
            return {
                "success": False,
                "error": "Token cannot be empty"
            }
        
        success = stockbit_client.update_token(body.token)
        
        return {
            "success": success,
            "message": "Token updated successfully" if success else "Failed to update token",
            **stockbit_client.get_status()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/stockbit/test")
async def test_stockbit_connection():
    """
    Test Stockbit connection with current token.
    
    Quick way to verify if token is working without making full analysis.
    """
    try:
        from app.services.stockbit_client import stockbit_client
        import asyncio
        
        # Test with a simple API call
        result = await stockbit_client.get_orderbook("BBCA")
        
        if result:
            return {
                "success": True,
                "message": "Token is valid and working",
                "sample_data": {
                    "symbol": result.get("symbol"),
                    "lastprice": result.get("lastprice"),
                    "source": result.get("source")
                },
                **stockbit_client.get_status()
            }
        else:
            return {
                "success": False,
                "message": "Token invalid or API error",
                **stockbit_client.get_status()
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

