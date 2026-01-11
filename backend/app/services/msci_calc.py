import math

def calculate_fif_2025(free_float_ratio: float, fol: float = 1.0, current_fif: float = None) -> float:
    """
    Calculates FIF based on MSCI 2025 Proposal with granular buckets and buffers.
    
    Args:
        free_float_ratio (float): The raw float (e.g., 0.157 for 15.7%)
        fol (float): Foreign Ownership Limit (0.0 to 1.0)
        current_fif (float, optional): The existing FIF, used for buffer checks.
    """
    # 1. Cap float at Foreign Ownership Limit
    effective_float = min(free_float_ratio, fol)
    
    # 2. Determine granularity bucket and buffer based on float level
    if effective_float > 0.25:
        bucket = 0.025
        buffer = 0.025
    elif 0.05 < effective_float <= 0.25:
        bucket = 0.005
        buffer = 0.005
    else:
        bucket = 0.001
        buffer = 0.001
        
    # 3. Calculate the potential new FIF (Rounded)
    # Logic: Round to nearest bucket
    # Example: 0.157 with bucket 0.005 -> 0.157 / 0.005 = 31.4 -> 31 * 0.005 = 0.155
    potential_fif = round(round(effective_float / bucket) * bucket, 3)
    
    # 4. Apply Buffer Logic (Hysteresis)
    if current_fif is not None:
        # Only change if the delta exceeds the buffer
        if abs(effective_float - current_fif) < buffer:
            return current_fif

    return potential_fif
