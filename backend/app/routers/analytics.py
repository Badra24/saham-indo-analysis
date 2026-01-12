from fastapi import APIRouter, HTTPException, Query
from app.services.analytics_service import analytics_service
from typing import Dict, List, Optional

router = APIRouter()

@router.get("/trend/{ticker}", response_model=List[Dict])
async def get_broker_trend(ticker: str, days: int = Query(30, ge=5, le=365)):
    """
    Get Historical Bandarmology Trend (Net Flow).
    Returns daily sequence of Institutional, Retail, and Foreign flow.
    """
    try:
        return analytics_service.get_net_flow_trend(ticker, days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/heatmap/{ticker}", response_model=List[Dict])
async def get_broker_heatmap(ticker: str, days: int = Query(30, ge=5, le=365)):
    """
    Get Broker Aggregated Heatmap.
    Returns Total Buy/Sell/Net per broker for the period.
    """
    try:
        return analytics_service.get_broker_heatmap(ticker, days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
