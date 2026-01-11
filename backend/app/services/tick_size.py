import math

def get_tick_size(price: float) -> int:
    """
    Returns the valid tick size for a given price based on IDX rules.
    < 200: Rp 1
    200 - < 500: Rp 2
    500 - < 2000: Rp 5
    2000 - < 5000: Rp 10
    >= 5000: Rp 25
    """
    if price < 200:
        return 1
    elif price < 500:
        return 2
    elif price < 2000:
        return 5
    elif price < 5000:
        return 10
    else:
        return 25

def normalize_price(price: float) -> float:
    """
    Rounds a raw price to the nearest valid IDX tick.
    """
    tick = get_tick_size(price)
    return round(price / tick) * tick

def get_ara_arb_limits(price: float) -> tuple[float, float]:
    """
    Calculates Symmetric Auto Rejection Limits (2025 Normalization).
    
    Rp 50 - Rp 200: 35%
    > Rp 200 - Rp 5000: 25%
    > Rp 5000: 20%
    
    Returns (ARB_Price, ARA_Price)
    """
    if price <= 200:
        limit = 0.35
    elif price <= 5000:
        limit = 0.25
    else:
        limit = 0.20
        
    lower_limit = normalize_price(price * (1 - limit))
    upper_limit = normalize_price(price * (1 + limit))
    
    return lower_limit, upper_limit
