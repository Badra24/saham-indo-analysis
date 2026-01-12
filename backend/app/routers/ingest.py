from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Dict, List, Optional
import csv
import io
from datetime import date
from app.services.database_service import db_service
from app.services.idx_static_data import get_broker_by_code

router = APIRouter()

@router.post("/ingest/upload_csv")
async def upload_csv_broker_summary(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    date_str: Optional[str] = Form(None)
):
    """
    Upload CSV Broker Summary (Stockbit Format)
    Columns expected: Broker, B.Vol, B.Val, B.Avg, S.Vol, S.Val, S.Avg
    """
    try:
        if not date_str:
            date_str = date.today().isoformat()
            
        content = await file.read()
        decoded = content.decode('utf-8')
        
        # Debug: Print first few lines to log
        lines = decoded.split('\n')
        print(f"[CSV DEBUG] Header: {lines[0] if lines else 'EMPTY'}")
        
        # Detect delimiter
        delimiter = ','
        if ';' in lines[0]:
            delimiter = ';'
        print(f"[CSV DEBUG] Detected delimiter: '{delimiter}'")
            
        reader = csv.DictReader(io.StringIO(decoded), delimiter=delimiter)
        
        top_buyers = []
        top_sellers = []
        
        total_buy_val = 0
        total_sell_val = 0
        
        inst_net = 0
        retail_net = 0
        foreign_net = 0
        
        # Helper: Parse Numbers with Suffixes (M/B/K)
        def parse_num(val):
            if not val: return 0.0
            val = str(val).upper().strip()
            val = val.replace('RP', '').replace(' ', '').replace(',', '.') 
            
            multiplier = 1.0
            if 'B' in val:
                multiplier = 1_000_000_000.0
                val = val.replace('B', '')
            elif 'M' in val:
                multiplier = 1_000_000.0
                val = val.replace('M', '')
            elif 'K' in val:
                multiplier = 1_000.0
                val = val.replace('K', '')
            
            try:
                return float(val) * multiplier
            except:
                return 0.0

        # Parse CSV Rows (Side-by-Side Format)
        for row in reader:
            keys = {k.strip(): v for k, v in row.items()}
            
            # --- PROCESS BUY SIDE ---
            buy_broker = keys.get('Broker (Buy)', '').strip()
            if buy_broker:
                # Get Info
                b_info = get_broker_by_code(buy_broker) or {}
                
                # Parse Values
                b_val = parse_num(keys.get('B.Val', keys.get('B. Val', 0)))
                b_vol = int(parse_num(keys.get('B.Lot', keys.get('B. Lot', keys.get('B.Vol', 0)))))
                
                if b_val > 0:
                    top_buyers.append({
                        "code": buy_broker,
                        "value": b_val,
                        "volume": b_vol,
                        "type": b_info.get('type', 'UNKNOWN'),
                        "is_foreign": b_info.get('is_foreign', False)
                    })
                    total_buy_val += b_val
                    
                    # Accumulate Net Flow Stats
                    # Note: In split format, we don't have per-row Net. We sum up totals.
                    # Net = Buy - Sell. We sum all Buys and all Sells separately.
                    if b_info.get('type') == 'INSTITUTION': inst_net += b_val
                    elif b_info.get('type') == 'RETAIL': retail_net += b_val
                    if b_info.get('is_foreign'): foreign_net += b_val

            # --- PROCESS SELL SIDE ---
            sell_broker = keys.get('Broker (Sell)', '').strip()
            if sell_broker:
                # Get Info
                s_info = get_broker_by_code(sell_broker) or {}
                
                # Parse Values
                s_val = parse_num(keys.get('S.Val', keys.get('S. Val', 0)))
                s_vol = int(parse_num(keys.get('S.Lot', keys.get('S. Lot', keys.get('S.Vol', 0)))))
                
                if s_val > 0:
                    top_sellers.append({
                        "code": sell_broker,
                        "value": s_val,
                        "volume": s_vol,
                        "type": s_info.get('type', 'UNKNOWN'),
                        "is_foreign": s_info.get('is_foreign', False)
                    })
                    total_sell_val += s_val
                    
                    # Accumulate Net Flow Stats (Subtract Sells)
                    if s_info.get('type') == 'INSTITUTION': inst_net -= s_val
                    elif s_info.get('type') == 'RETAIL': retail_net -= s_val
                    if s_info.get('is_foreign'): foreign_net -= s_val

        # Sort Lists (Value Descending)
        top_buyers.sort(key=lambda x: x['value'], reverse=True)
        top_sellers.sort(key=lambda x: x['value'], reverse=True)

        # Compute Concentration (Top 3 Buyers vs Sellers)
        top3_buy = sum(x['value'] for x in top_buyers[:3])
        top3_sell = sum(x['value'] for x in top_sellers[:3])
        
        # REAL Logic for Stats (Bandarmology)
        # Calculate dominance of Top 3 players
        top3_buy_pct = (top3_buy / total_buy_val * 100) if total_buy_val > 0 else 0
        top3_sell_pct = (top3_sell / total_sell_val * 100) if total_sell_val > 0 else 0
        
        # Accumulation: Big players buying more than selling, AND they dominate the buy side
        if top3_buy > top3_sell * 1.1:
            status = "ACCUMULATION"
            if top3_buy > top3_sell * 1.5: status = "BIG_ACCUMULATION"
            conc_ratio = top3_buy_pct
        elif top3_sell > top3_buy * 1.1:
            status = "DISTRIBUTION"
            if top3_sell > top3_buy * 1.5: status = "BIG_DISTRIBUTION"
            conc_ratio = top3_sell_pct
        else:
            status = "NEUTRAL"
            conc_ratio = (top3_buy_pct + top3_sell_pct) / 2 # Average dominance
            
        data = {
            "status": status,
            "concentration_ratio": conc_ratio,
            "institutional_net_flow": inst_net,
            "retail_net_flow": retail_net,
            "foreign_net_flow": foreign_net,
            "top_buyers": top_buyers,
            "top_sellers": top_sellers,
            "total_value": total_buy_val, # for backward compat
            "buy_value": total_buy_val,
            "sell_value": total_sell_val,
            "net_value": total_buy_val - total_sell_val
        }
        
        # Save to DB
        db_service.insert_broker_summary(ticker, date_str, data, source="upload")
        
        return {"status": "success", "message": f"Ingested {len(top_buyers)} buyers and {len(top_sellers)} sellers for {ticker}", "data": data}

    except Exception as e:
        print(f"Error parsing CSV: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
