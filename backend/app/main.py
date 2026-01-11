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
    yield
    print("👋 Shutting down...")


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
