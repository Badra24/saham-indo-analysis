"""
File Upload Service for Broker Summary and Financial Reports

Supports:
- PDF parsing (Stockbit-style broker summary)
- CSV/Excel parsing for structured data
- Financial report extraction
- Image OCR (Tesseract) for screenshots

Based on research documents:
- Bandar Saham: Advanced Identification & Expert Insights
- Valuasi, Akumulasi, dan Risiko (Alpha-V System)
"""

import io
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from pathlib import Path

import pandas as pd

from app.models.file_models import (
    FileType, BrokerType, BrokerEntry, BrokerSummaryData,
    FinancialReportData, FileUploadResponse
)

logger = logging.getLogger(__name__)

# ============================================================================
# BROKER CODE CLASSIFICATION (From Research)
# ============================================================================

# Institutional Foreign Brokers (from research)
INSTITUTIONAL_FOREIGN_CODES = {"AK", "BK", "ZP", "KZ", "RX", "MS", "CS", "UB", "DB", "JP"}

# Institutional Local "Whale" Brokers
INSTITUTIONAL_LOCAL_CODES = {"MG", "RF", "HP", "KI", "DX"}

# Retail Platform Brokers (potential disguise channels per research)
RETAIL_PLATFORM_CODES = {"XL", "XC", "YP", "PD", "CC", "NI", "LG", "AI"}


def classify_broker(code: str) -> Tuple[BrokerType, bool]:
    """
    Classify broker code based on research categorization.
    Returns (BrokerType, is_foreign)
    """
    code_upper = code.upper().strip()
    
    if code_upper in INSTITUTIONAL_FOREIGN_CODES:
        return BrokerType.INSTITUTIONAL_FOREIGN, True
    elif code_upper in INSTITUTIONAL_LOCAL_CODES:
        return BrokerType.INSTITUTIONAL_LOCAL, False
    elif code_upper in RETAIL_PLATFORM_CODES:
        return BrokerType.RETAIL_PLATFORM, False
    else:
        return BrokerType.UNKNOWN, False


def validate_file_type(filename: str) -> FileType:
    """Determine file type from filename extension"""
    if not filename:
        return FileType.UNKNOWN
    
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return FileType.PDF
    elif ext == ".csv":
        return FileType.CSV
    elif ext in [".xlsx", ".xls"]:
        return FileType.EXCEL
    else:
        return FileType.UNKNOWN


# ============================================================================
# CSV/EXCEL PARSER
# ============================================================================

def parse_broker_summary_csv(
    content: bytes,
    ticker: str,
    filename: str = None
) -> BrokerSummaryData:
    """
    Parse CSV/Excel broker summary file.
    
    Supports TWO formats:
    
    1. Stockbit Side-by-Side Format:
       Broker (Buy) | B.Val | B.Lot | Broker (Sell) | S.Val | S.Lot
       ZP           | 2.7B  | 77.6K | AK            | 3.9B  | 111.2K
    
    2. Generic Row Format:
       Broker | Buy Value | Sell Value | Net
       ZP     | 2.7B      | 0          | 2.7B
    """
    try:
        # Try to read as CSV first, then Excel
        try:
            df = pd.read_csv(io.BytesIO(content))
        except:
            df = pd.read_excel(io.BytesIO(content))
        
        # Normalize column names
        df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
        
        # Detect format: Side-by-Side (Stockbit) vs Generic
        is_stockbit_format = (
            any('broker_(buy)' in col or 'broker_buy' in col for col in df.columns) or
            any('broker_(sell)' in col or 'broker_sell' in col for col in df.columns)
        )
        
        buyers = []
        sellers = []
        total_buy = 0
        total_sell = 0
        foreign_buy = 0
        foreign_sell = 0
        
        if is_stockbit_format:
            # --- STOCKBIT SIDE-BY-SIDE FORMAT ---
            # Find buy-side columns
            buy_broker_col = _find_column(df, ["broker_(buy)", "broker_buy"])
            buy_val_col = _find_column(df, ["b.val", "bval", "buy_val", "b_val"])
            buy_lot_col = _find_column(df, ["b.lot", "blot", "buy_lot", "b_lot"])
            
            # Find sell-side columns
            sell_broker_col = _find_column(df, ["broker_(sell)", "broker_sell"])
            sell_val_col = _find_column(df, ["s.val", "sval", "sell_val", "s_val"])
            sell_lot_col = _find_column(df, ["s.lot", "slot", "sell_lot", "s_lot"])
            
            for _, row in df.iterrows():
                # Parse buyer
                buyer_code = str(row.get(buy_broker_col, "")).strip().upper()
                if buyer_code and buyer_code != "NAN" and buyer_code != "-":
                    buy_value = _safe_float(row.get(buy_val_col, 0))
                    buy_volume = _safe_float(row.get(buy_lot_col, 0)) * 100  # Lot to shares
                    
                    broker_type, is_foreign = classify_broker(buyer_code)
                    
                    entry = BrokerEntry(
                        broker_code=buyer_code,
                        broker_type=broker_type,
                        buy_value=buy_value,
                        sell_value=0,
                        buy_volume=buy_volume,
                        sell_volume=0,
                        net_value=buy_value,
                        net_volume=buy_volume,
                        is_foreign=is_foreign
                    )
                    buyers.append(entry)
                    total_buy += buy_value
                    if is_foreign:
                        foreign_buy += buy_value
                    
                    # Debug logging
                    logger.info(f"[UPLOAD-PARSE] Buyer: {buyer_code} | Type: {broker_type.value} | Foreign: {is_foreign} | Value: {buy_value:,.0f}")
                
                # Parse seller
                seller_code = str(row.get(sell_broker_col, "")).strip().upper()
                if seller_code and seller_code != "NAN" and seller_code != "-":
                    sell_value = _safe_float(row.get(sell_val_col, 0))
                    sell_volume = _safe_float(row.get(sell_lot_col, 0)) * 100
                    
                    broker_type, is_foreign = classify_broker(seller_code)
                    
                    entry = BrokerEntry(
                        broker_code=seller_code,
                        broker_type=broker_type,
                        buy_value=0,
                        sell_value=sell_value,
                        buy_volume=0,
                        sell_volume=sell_volume,
                        net_value=-sell_value,
                        net_volume=-sell_volume,
                        is_foreign=is_foreign
                    )
                    sellers.append(entry)
                    total_sell += sell_value
                    if is_foreign:
                        foreign_sell += sell_value
                    
                    # Debug logging
                    logger.info(f"[UPLOAD-PARSE] Seller: {seller_code} | Type: {broker_type.value} | Foreign: {is_foreign} | Value: {sell_value:,.0f}")
        else:
            # --- GENERIC ROW FORMAT ---
            broker_col = _find_column(df, ["broker", "broker_code", "kode_broker", "code"])
            buy_col = _find_column(df, ["buy_value", "buy", "beli", "buy_val", "b_value"])
            sell_col = _find_column(df, ["sell_value", "sell", "jual", "sell_val", "s_value"])
            buy_vol_col = _find_column(df, ["buy_volume", "buy_vol", "b_vol", "b_volume"])
            sell_vol_col = _find_column(df, ["sell_volume", "sell_vol", "s_vol", "s_volume"])
            
            if not broker_col or (not buy_col and not sell_col):
                raise ValueError("Required columns not found: broker and buy/sell values")
            
            for _, row in df.iterrows():
                broker_code = str(row.get(broker_col, "")).strip().upper()
                if not broker_code or broker_code == "NAN":
                    continue
                
                buy_value = _safe_float(row.get(buy_col, 0))
                sell_value = _safe_float(row.get(sell_col, 0))
                buy_volume = _safe_float(row.get(buy_vol_col, 0)) if buy_vol_col else 0
                sell_volume = _safe_float(row.get(sell_vol_col, 0)) if sell_vol_col else 0
                
                broker_type, is_foreign = classify_broker(broker_code)
                
                entry = BrokerEntry(
                    broker_code=broker_code,
                    broker_type=broker_type,
                    buy_value=buy_value,
                    sell_value=sell_value,
                    buy_volume=buy_volume,
                    sell_volume=sell_volume,
                    net_value=buy_value - sell_value,
                    net_volume=buy_volume - sell_volume,
                    is_foreign=is_foreign
                )
                
                total_buy += buy_value
                total_sell += sell_value
                
                if is_foreign:
                    foreign_buy += buy_value
                    foreign_sell += sell_value
                
                if buy_value > sell_value:
                    buyers.append(entry)
                else:
                    sellers.append(entry)
        
        # Sort by net value
        buyers.sort(key=lambda x: x.net_value, reverse=True)
        sellers.sort(key=lambda x: x.net_value)  # Most negative first
        
        # Take top 5 each
        top_buyers = buyers[:5]
        top_sellers = sellers[:5]
        
        # Calculate BCR (Broker Concentration Ratio) from research
        top3_buyer_val = sum(b.buy_value for b in top_buyers[:3])
        top3_seller_val = sum(abs(s.sell_value) for s in top_sellers[:3])
        
        bcr = top3_buyer_val / top3_seller_val if top3_seller_val > 0 else 1.0
        
        # BCR interpretation from research
        if bcr > 2.0:
            bcr_interp = "STRONG_ACCUMULATION"
            phase = "ACCUMULATION"
        elif bcr > 1.2:
            bcr_interp = "MODERATE_ACCUMULATION"
            phase = "ACCUMULATION"
        elif bcr < 0.5:
            bcr_interp = "STRONG_DISTRIBUTION"
            phase = "DISTRIBUTION"
        elif bcr < 0.8:
            bcr_interp = "MODERATE_DISTRIBUTION"
            phase = "DISTRIBUTION"
        else:
            bcr_interp = "NEUTRAL"
            phase = "NEUTRAL"
        
        # Detect retail disguise (from Bandar research)
        retail_disguise_signals = _detect_retail_disguise(top_buyers, top_sellers)
        
        # Calculate Smart Money Flow score for Alpha-V
        smf_score = _calculate_smf_score(bcr, foreign_buy, foreign_sell, total_buy + total_sell)
        
        total_value = total_buy + total_sell
        
        # Summary logging
        logger.info(f"[UPLOAD-PARSE] ====== SUMMARY FOR {ticker.upper()} ======")
        logger.info(f"[UPLOAD-PARSE] Total Buyers: {len(buyers)} | Total Sellers: {len(sellers)}")
        logger.info(f"[UPLOAD-PARSE] Total Buy: {total_buy:,.0f} | Total Sell: {total_sell:,.0f}")
        logger.info(f"[UPLOAD-PARSE] Foreign Buy: {foreign_buy:,.0f} | Foreign Sell: {foreign_sell:,.0f}")
        logger.info(f"[UPLOAD-PARSE] Net Foreign: {foreign_buy - foreign_sell:,.0f}")
        logger.info(f"[UPLOAD-PARSE] BCR: {bcr:.3f} | Phase: {phase}")
        logger.info(f"[UPLOAD-PARSE] Top 5 Buyers: {[b.broker_code for b in top_buyers]}")
        logger.info(f"[UPLOAD-PARSE] Top 5 Sellers: {[s.broker_code for s in top_sellers]}")
        logger.info(f"[UPLOAD-PARSE] =====================================")

        return BrokerSummaryData(
            ticker=ticker.upper(),
            date=date.today().isoformat(),
            source="upload",
            top_buyers=top_buyers,
            top_sellers=top_sellers,
            bcr=round(bcr, 3),
            bcr_interpretation=bcr_interp,
            foreign_buy=foreign_buy,
            foreign_sell=foreign_sell,
            net_foreign_flow=foreign_buy - foreign_sell,
            foreign_flow_pct=round(((foreign_buy + foreign_sell) / total_value * 100) if total_value > 0 else 0, 2),
            smf_score=smf_score,
            retail_disguise_detected=len(retail_disguise_signals) > 0,
            retail_disguise_signals=retail_disguise_signals,
            phase=phase,
            phase_confidence=min(abs(bcr - 1.0) / 1.0, 1.0),
            total_buy=total_buy,
            total_sell=total_sell,
            total_transaction_value=total_value,
            total_transaction_volume=sum(b.buy_volume + b.sell_volume for b in buyers + sellers),
            file_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error parsing broker summary CSV: {e}")
        raise ValueError(f"Failed to parse broker summary: {str(e)}")


def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Find first matching column from candidates"""
    for col in df.columns:
        for candidate in candidates:
            if candidate in col:
                return col
    return None


def _safe_float(val) -> float:
    """
    Safely convert value to float.
    Handles abbreviated formats: 2.7B, 77.6K, 936.3M
    Also handles Indonesian decimal commas: 2,7B
    """
    if pd.isna(val) or val == '-':
        return 0.0
    try:
        if isinstance(val, (int, float)):
            return float(val)
        
        # Normalize string: uppercase, strip whitespace
        val_str = str(val).strip().upper()
        
        # Detect suffix multiplier
        multiplier = 1.0
        if val_str.endswith('B'):
            multiplier = 1_000_000_000
            val_str = val_str[:-1]
        elif val_str.endswith('M'):
            multiplier = 1_000_000
            val_str = val_str[:-1]
        elif val_str.endswith('K'):
            multiplier = 1_000
            val_str = val_str[:-1]
        
        # Handle decimal separator: replace comma with dot ONLY if multiple digits follow
        # or if it looks like a decimal (e.g., 2,7 vs 2,700)
        # Actually, in Stockbit values (111.2K or 111,2K), the separator is a decimal.
        # We replace ',' with '.' after stripping common thousand separators if any.
        # Simple heuristic: if we have both . and , then . is thousand and , is decimal.
        if ',' in val_str and '.' in val_str:
            val_str = val_str.replace('.', '').replace(',', '.')
        elif ',' in val_str:
            val_str = val_str.replace(',', '.')
            
        return float(val_str) * multiplier
    except:
        return 0.0


def _detect_retail_disguise(buyers: List[BrokerEntry], sellers: List[BrokerEntry]) -> List[str]:
    """
    Detect signs of institutional activity disguised as retail.
    Based on research: "Retail code behaving with institutional discipline is the strongest signal"
    """
    signals = []
    
    # Check if retail brokers are dominant buyers (suspicious if concentrated)
    for buyer in buyers[:3]:
        if buyer.broker_type == BrokerType.RETAIL_PLATFORM:
            # High concentration from retail broker suggests disguise
            if buyer.net_value > 0:
                pct = buyer.buy_value / sum(b.buy_value for b in buyers if b.buy_value > 0) * 100
                if pct > 30:
                    signals.append(
                        f"High concentration from retail broker {buyer.broker_code} ({pct:.1f}%) - possible disguised accumulation"
                    )
    
    # Check for institutional sellers + retail buyers pattern
    inst_sellers = [s for s in sellers if s.broker_type in [BrokerType.INSTITUTIONAL_FOREIGN, BrokerType.INSTITUTIONAL_LOCAL]]
    retail_buyers = [b for b in buyers if b.broker_type == BrokerType.RETAIL_PLATFORM]
    
    if len(inst_sellers) > 0 and len(retail_buyers) > 0:
        # This could be distribution phase
        total_inst_sell = sum(abs(s.net_value) for s in inst_sellers)
        total_retail_buy = sum(b.net_value for b in retail_buyers if b.net_value > 0)
        
        if total_retail_buy > total_inst_sell * 0.5:
            signals.append(
                "Pattern: Institutional selling with retail buying - possible distribution phase"
            )
    
    return signals


def _calculate_smf_score(bcr: float, foreign_buy: float, foreign_sell: float, total_value: float) -> float:
    """
    Calculate Smart Money Flow score for Alpha-V system (0-100).
    Based on BCR and foreign flow metrics from research.
    """
    score = 50  # Start neutral
    
    # BCR component (0-50 points)
    if bcr > 1.5:
        score += min(50, (bcr - 1.0) * 50)
    elif bcr < 0.8:
        score -= min(50, (1.0 - bcr) * 60)
    
    # Foreign flow component (0-30 points)
    if total_value > 0:
        net_foreign = foreign_buy - foreign_sell
        foreign_pct = net_foreign / total_value * 100
        if foreign_pct > 20:
            score += 30
        elif foreign_pct > 10:
            score += 20
        elif foreign_pct > 0:
            score += 10
        elif foreign_pct < -20:
            score -= 30
        elif foreign_pct < -10:
            score -= 20
        elif foreign_pct < 0:
            score -= 10
    
    return max(0, min(100, score))


# ============================================================================
# PDF PARSER
# ============================================================================

def parse_broker_summary_pdf(
    content: bytes,
    ticker: str,
    filename: str = None
) -> BrokerSummaryData:
    """
    Parse PDF broker summary file (Stockbit-style).
    
    Uses pdfplumber to extract tables from PDF.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required for PDF parsing. Install with: pip install pdfplumber")
    
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            all_text = ""
            all_tables = []
            
            for page in pdf.pages:
                all_text += page.extract_text() or ""
                tables = page.extract_tables()
                all_tables.extend(tables)
            
            if not all_tables:
                raise ValueError("No tables found in PDF")
            
            # Find the broker summary table (usually largest)
            main_table = max(all_tables, key=lambda t: len(t))
            
            # Convert to DataFrame
            header = main_table[0]
            data = main_table[1:]
            df = pd.DataFrame(data, columns=header)
            
            # Use CSV parser logic
            csv_bytes = df.to_csv(index=False).encode()
            return parse_broker_summary_csv(csv_bytes, ticker, filename)
            
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        raise ValueError(f"Failed to parse PDF broker summary: {str(e)}")


# ============================================================================
# IMAGE OCR PARSER (Tesseract)
# ============================================================================

def parse_broker_summary_image(
    content: bytes,
    ticker: str,
    filename: str = None
) -> BrokerSummaryData:
    """
    Parse Stockbit/Ajaib screenshot using Tesseract OCR.
    
    Split-Processing Logic:
    1. Load image and split vertically in half (Buy on left, Sell on right)
    2. Preprocess both halves independently
    3. Run OCR on each half
    4. Extract entries and aggregate
    """
    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageOps
        import cv2
        import numpy as np
    except ImportError as e:
        raise ImportError(f"OCR dependencies missing: {e}. Install with: pip install pytesseract pillow opencv-python")
    
    try:
        # Load image
        full_img = Image.open(io.BytesIO(content))
        width, height = full_img.size
        
        # Split image vertically
        left_half = full_img.crop((0, 0, width // 2, height))
        right_half = full_img.crop((width // 2, 0, width, height))
        
        def process_half(img, side_label="SIDE"):
            # Preprocess: grayscale
            img = img.convert('L')
            
            # INVERT IMAGE: Dark mode text (white on black) -> black on white
            # This significantly improves OCR accuracy for colored text on dark backgrounds
            img = ImageOps.invert(img)
            
            # Enhance contrast significantly
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(3.5) # Increased to 3.5
            
            # Brightness adjustment
            brightness = ImageEnhance.Brightness(img)
            img = brightness.enhance(1.2)
            
            # Convert to numpy for OpenCV for denoising
            img_np = np.array(img)
            
            # Denoise
            img_np = cv2.medianBlur(img_np, 1) # Gentle denoising
            
            # Thresholding
            _, img_np = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Sharpen using kernel
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            img_np = cv2.filter2D(img_np, -1, kernel)
            
            # Convert back to PIL
            processed_img = Image.fromarray(img_np)
            
            # OCR
            custom_config = r'--oem 3 --psm 6'
            extracted_text = pytesseract.image_to_string(processed_img, config=custom_config)
            logger.info(f"[OCR-{side_label}] Text: {extracted_text[:300]}...") # Log more text
            return extracted_text

        text_buy = process_half(left_half, "BUY")
        text_sell = process_half(right_half, "SELL")
        
        # 4. Parse extracted text
        buyers = []
        sellers = []
        total_buy = 0
        total_sell = 0
        foreign_buy = 0
        foreign_sell = 0
        
        # Regex pattern for broker entries: [Code] [Value] [Volume] [Avg]
        # Robust pattern to handle dots/commas and suffixes
        broker_pattern = re.compile(
            r'([A-Z]{2})\s+([\d.,]+[BMK]?)\s+([\d.,]+[BMK]?)', 
            re.IGNORECASE
        )
        
        # Process Buy Side
        for line in text_buy.split('\n'):
            matches = broker_pattern.findall(line)
            for match in matches:
                broker_code = match[0].upper()
                if broker_code in ['BB', 'SB', 'SV', 'BT', 'ST', 'AV']: continue # Header noise
                
                value = _safe_float(match[1])
                volume = _safe_float(match[2]) * 100 # Lot to shares
                
                broker_type, is_foreign = classify_broker(broker_code)
                entry = BrokerEntry(
                    broker_code=broker_code,
                    broker_type=broker_type,
                    buy_value=value,
                    sell_value=0,
                    buy_volume=volume,
                    sell_volume=0,
                    net_value=value,
                    net_volume=volume,
                    is_foreign=is_foreign
                )
                buyers.append(entry)
                total_buy += value
                if is_foreign:
                    foreign_buy += value

        # Process Sell Side
        for line in text_sell.split('\n'):
            matches = broker_pattern.findall(line)
            for match in matches:
                broker_code = match[0].upper()
                if broker_code in ['BB', 'SB', 'SV', 'BT', 'ST', 'AV']: continue # Header noise

                value = _safe_float(match[1])
                volume = _safe_float(match[2]) * 100
                
                broker_type, is_foreign = classify_broker(broker_code)
                entry = BrokerEntry(
                    broker_code=broker_code,
                    broker_type=broker_type,
                    buy_value=0,
                    sell_value=value,
                    buy_volume=0,
                    sell_volume=volume,
                    net_value=-value,
                    net_volume=-volume,
                    is_foreign=is_foreign
                )
                sellers.append(entry)
                total_sell += value
                if is_foreign:
                    foreign_sell += value
        
        # Deduplicate and consolidate (if same broker appears twice due to OCR overlap)
        def consolidate(entries):
            merged = {}
            for e in entries:
                if e.broker_code not in merged:
                    merged[e.broker_code] = e
                else:
                    curr = merged[e.broker_code]
                    curr.buy_value += e.buy_value
                    curr.sell_value += e.sell_value
                    curr.buy_volume += e.buy_volume
                    curr.sell_volume += e.sell_volume
                    curr.net_value += e.net_value
                    curr.net_volume += e.net_volume
            return list(merged.values())

        buyers = consolidate(buyers)
        sellers = consolidate(sellers)

        # Sort and take top 5
        buyers.sort(key=lambda x: x.net_value, reverse=True)
        sellers.sort(key=lambda x: x.net_value)
        
        top_buyers = buyers[:5]
        top_sellers = sellers[:5]
        
        # Calculate BCR
        top3_buyer_val = sum(b.buy_value for b in top_buyers[:3])
        top3_seller_val = sum(abs(s.sell_value) for s in top_sellers[:3])
        bcr = top3_buyer_val / top3_seller_val if top3_seller_val > 0 else 1.0
        
        # BCR interpretation
        if bcr > 2.0:
            bcr_interp = "STRONG_ACCUMULATION"
            phase = "ACCUMULATION"
        elif bcr > 1.2:
            bcr_interp = "MODERATE_ACCUMULATION"
            phase = "ACCUMULATION"
        elif bcr < 0.5:
            bcr_interp = "STRONG_DISTRIBUTION"
            phase = "DISTRIBUTION"
        elif bcr < 0.8:
            bcr_interp = "MODERATE_DISTRIBUTION"
            phase = "DISTRIBUTION"
        else:
            bcr_interp = "NEUTRAL"
            phase = "NEUTRAL"
        
        total_value = total_buy + total_sell
        smf_score = _calculate_smf_score(bcr, foreign_buy, foreign_sell, total_value)
        
        return BrokerSummaryData(
            ticker=ticker.upper(),
            date=date.today().isoformat(),
            source="ocr_upload",
            top_buyers=top_buyers,
            top_sellers=top_sellers,
            bcr=round(bcr, 3),
            bcr_interpretation=bcr_interp,
            foreign_buy=foreign_buy,
            foreign_sell=foreign_sell,
            net_foreign_flow=foreign_buy - foreign_sell,
            foreign_flow_pct=round(((foreign_buy + foreign_sell) / total_value * 100) if total_value > 0 else 0, 2),
            smf_score=smf_score,
            retail_disguise_detected=False,
            retail_disguise_signals=[],
            phase=phase,
            phase_confidence=min(abs(bcr - 1.0) / 1.0, 1.0),
            total_buy=total_buy,
            total_sell=total_sell,
            total_transaction_value=total_value,
            total_transaction_volume=sum(b.buy_volume + b.sell_volume for b in buyers + sellers),
            file_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error parsing image with OCR: {e}")
        raise ValueError(f"Failed to parse image: {str(e)}")


# ============================================================================
# FINANCIAL REPORT PARSER
# ============================================================================

def parse_financial_report_pdf(
    content: bytes,
    ticker: str,
    filename: str = None
) -> FinancialReportData:
    """
    Parse IDX PDF financial statements.
    Extracts key metrics using table extraction.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber required for PDF parsing")
    
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            metrics = {}
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row and len(row) >= 2:
                            label = str(row[0] or "").strip().lower()
                            value = str(row[-1] or "").strip()
                            if any(k in label for k in ["per", "p/e"]):
                                metrics["per"] = _safe_float(value)
                            elif any(k in label for k in ["pbv", "p/b"]):
                                metrics["pbv"] = _safe_float(value)
                            elif any(k in label for k in ["roe", "return on equity"]):
                                metrics["roe"] = _safe_float(value)
                            elif any(k in label for k in ["roa", "return on asset"]):
                                metrics["roa"] = _safe_float(value)
                            elif any(k in label for k in ["npm", "net profit margin"]):
                                metrics["npm"] = _safe_float(value)
                            elif any(k in label for k in ["der", "debt to equity"]):
                                metrics["der"] = _safe_float(value)
                            elif any(k in label for k in ["current ratio"]):
                                metrics["current_ratio"] = _safe_float(value)
                            elif any(k in label for k in ["laba bersih", "net income", "profit"]):
                                metrics["net_income"] = _safe_float(value)
                            elif any(k in label for k in ["ev/ebitda", "ev to ebitda", "enterprise value"]):
                                metrics["ev_ebitda"] = _safe_float(value)
                            elif any(k in label for k in ["pcf", "price to cash flow", "price/cash flow"]):
                                metrics["pcf"] = _safe_float(value)
                            elif any(k in label for k in ["ocf", "operating cash flow", "arus kas operasi", "kas dari aktivitas operasi"]):
                                metrics["ocf"] = _safe_float(value)
                            elif any(k in label for k in ["revenue", "pendapatan", "sales", "penjualan"]):
                                # Simple heuristic for revenue if needed, though growth is usually calc'd
                                pass 
            
            # Fallback: Text-based extraction if tables are empty or insufficient
            if len(metrics) < 3:
                print("[DEBUG-PDF] Table extraction insufficient. Attempting text-based regex extraction.")
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"
                
                print(f"[DEBUG-PDF] Raw Text Snippet (First 500 chars):\n{full_text[:500]}")
                print(f"[DEBUG-PDF] Raw Text Snippet (Search Area):\n{full_text[(len(full_text)//2)-300:(len(full_text)//2)+300]}") # Middle of doc

                # Regex patterns for key metrics
                # Matches: "Label ... 123.45" or "Label 123.45" or "Label: 123.45"
                # Improved to handle multiline or different separators
                patterns = {
                    "per": [r"PER\s*[:]?\s*(\d+(?:\.\d+)?)", r"Price to Earnings\s*[:]?\s*(\d+(?:\.\d+)?)", r"P/E Ratio\s*[:]?\s*(\d+(?:\.\d+)?)"],
                    "pbv": [r"PBV\s*[:]?\s*(\d+(?:\.\d+)?)", r"Price to Book\s*[:]?\s*(\d+(?:\.\d+)?)", r"P/B Ratio\s*[:]?\s*(\d+(?:\.\d+)?)"],
                    "ev_ebitda": [r"EV/EBITDA\s*[:]?\s*(\d+(?:\.\d+)?)", r"Enterprise Value to EBITDA\s*[:]?\s*(\d+(?:\.\d+)?)"],
                    "pcf": [r"PCF\s*[:]?\s*(\d+(?:\.\d+)?)", r"Price to Cash Flow\s*[:]?\s*(\d+(?:\.\d+)?)", r"Diff.*Cash Flow\s*(\d+(?:\.\d+)?)"],
                    "roe": [r"ROE\s*[:]?\s*(\d+(?:\.\d+)?)", r"Return on Equity\s*[:]?\s*(\d+(?:\.\d+)?)"],
                    "der": [r"DER\s*[:]?\s*(\d+(?:\.\d+)?)", r"Debt to Equity\s*[:]?\s*(\d+(?:\.\d+)?)"],
                    "ocf": [
                        r"Operating Cash Flow\s*[:]?\s*([-]?\d+(?:[\.,]\d+)?)",
                        r"Arus Kas.*?Aktivitas Operasi\s*[:]?\s*\(?([-]?\d+(?:[\.,]\d+)?)\)?", 
                        r"Kas Bersih Diperoleh dari Aktivitas Operasi\s*[:]?\s*\(?([-]?\d+(?:[\.,]\d+)?)\)?"
                    ],
                    "net_income": [
                        r"Net Income\s*[:]?\s*([-]?\d+(?:[\.,]\d+)?)", 
                        r"Laba.*Periode Berjalan\s*[:]?\s*\(?([-]?\d+(?:[\.,]\d+)?)\)?",
                        r"Laba.*Tahun Berjalan\s*[:]?\s*\(?([-]?\d+(?:[\.,]\d+)?)\)?"
                    ],
                    "total_equity": [
                        r"Total Equity\s*[:]?\s*([-]?\d+(?:[\.,]\d+)?)",
                        r"Total Ekuitas\s*[:]?\s*([-]?\d+(?:[\.,]\d+)?)\)?",
                        r"Jumlah Ekuitas\s*[:]?\s*([-]?\d+(?:[\.,]\d+)?)\)?"
                    ]
                }
                
                import re
                for key, regex_list in patterns.items():
                    if key not in metrics:
                        for pattern in regex_list:
                            # Search in the whole text (or specific pages if we could segment)
                            # Using DOTALL to allow .* to match across lines if needed, but safe regex uses exact phrases
                            match = re.search(pattern, full_text, re.IGNORECASE)
                            if match:
                                val_str = match.group(1).replace(".", "").replace(",", ".") # INDO format: 1.000,00 -> 1000.00
                                try:
                                    # Very basic heuristic: if value is < 1000, assume it's a ratio. If > 1000, it's a raw value
                                    val = float(val_str)
                                    print(f"[DEBUG-PDF] Regex Match: {key} = {val} (Pattern: {pattern})")
                                    metrics[key] = val
                                    break
                                except:
                                    pass

            print(f"[DEBUG-PDF] Final Extracted Metrics: {metrics}")

            # Calculate derived if needed
            ocf = metrics.get("ocf")
            net_income = metrics.get("net_income")
            
            return FinancialReportData(
                ticker=ticker.upper(),
                period=datetime.now().strftime("%Y"),
                source="upload",
                per=metrics.get("per"),
                pbv=metrics.get("pbv"),
                pcf=metrics.get("pcf"),
                ev_ebitda=metrics.get("ev_ebitda"),
                roe=metrics.get("roe"),
                roa=metrics.get("roa"),
                npm=metrics.get("npm"),
                ocf=ocf,
                net_income=net_income,
                ocf_to_net_income=ocf / net_income if ocf and net_income and net_income != 0 else None,
                der=metrics.get("der"),
                current_ratio=metrics.get("current_ratio"),
                revenue_growth=None, # Hard to calc from single PDF without context
                earnings_growth=None,
                sector=None,
                file_name=filename
            )
            
    except Exception as e:
        logger.error(f"Error parsing financial report PDF: {e}")
        raise ValueError(f"Failed to parse financial report PDF: {str(e)}")


def parse_financial_report(
    content: bytes,
    ticker: str,
    filename: str = None,
    file_type: FileType = FileType.CSV
) -> FinancialReportData:
    """
    Parse financial report from CSV/Excel.
    
    Expected format:
    Metric | Value
    PER    | 15.2
    PBV    | 2.1
    ...
    """
    try:
        if file_type == FileType.CSV:
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        # Normalize columns
        df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
        
        # Try to extract key metrics
        metrics = {}
        
        # Check if it's a metric-value format or a wide format
        if len(df.columns) == 2:
            # Metric | Value format
            for _, row in df.iterrows():
                metric = str(row.iloc[0]).strip().lower()
                value = _safe_float(row.iloc[1])
                metrics[metric] = value
        else:
            # Wide format - columns are metrics
            if len(df) > 0:
                for col in df.columns:
                    metrics[col] = _safe_float(df[col].iloc[-1])  # Latest value
        
        # Map to FinancialReportData
        def get_metric(keys: List[str]) -> Optional[float]:
            # primary check: exact or close match
            for k in keys:
                # normalize search key
                k_norm = k.lower().replace(" ", "").replace("_", "").replace("/", "").replace("-", "")
                
                for m_key, val in metrics.items():
                    # normalize metric key from file
                    m_norm = str(m_key).lower().replace(" ", "").replace("_", "").replace("/", "").replace("-", "")
                    
                    if k_norm == m_norm or k_norm in m_norm:
                        return val
            return None
            
        print(f"[DEBUG] Parsed Metrics Keys: {list(metrics.keys())}")

        ocf = get_metric(["ocf", "operating_cash_flow", "arus_kas_operasi", "cash_flow_from_operations", "operating_cashflow"])
        net_income = get_metric(["net_income", "laba_bersih", "profit", "earnings", "net_profit"])
        
        # Calculate derived metrics if missing
        val_ev_ebitda = get_metric(["ev_ebitda", "ev/ebitda", "enterprise_value_to_ebitda", "ev_to_ebitda"])
        val_pcf = get_metric(["pcf", "p/cf", "price_to_cash_flow", "price_to_cash", "price_cash_flow"])
        
        print(f"[DEBUG] Extracted: EV/EBITDA={val_ev_ebitda}, PCF={val_pcf}")

        return FinancialReportData(
            ticker=ticker.upper(),
            period=datetime.now().strftime("%Y"),
            source="upload",
            per=get_metric(["per", "p/e", "price_to_earnings", "price_earnings_ratio"]),
            pbv=get_metric(["pbv", "p/b", "price_to_book", "price_book_value"]),
            pcf=val_pcf,
            ev_ebitda=val_ev_ebitda,
            roe=get_metric(["roe", "return_on_equity"]),
            roa=get_metric(["roa", "return_on_asset"]),
            npm=get_metric(["npm", "net_profit_margin", "margin_laba"]),
            ocf=ocf,
            net_income=net_income,
            ocf_to_net_income=ocf / net_income if ocf and net_income and net_income != 0 else None,
            der=get_metric(["der", "debt_to_equity", "d/e"]),
            current_ratio=get_metric(["current_ratio", "rasio_lancar"]),
            revenue_growth=get_metric(["revenue_growth", "growth", "pertumbuhan", "revenue"]),
            earnings_growth=get_metric(["earnings_growth", "profit_growth", "laba_growth"]),
            sector=get_metric(["sector", "sektor"]),
            file_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error parsing financial report: {e}")
        raise ValueError(f"Failed to parse financial report: {str(e)}")


# ============================================================================
# UNIFIED UPLOAD HANDLER
# ============================================================================

async def handle_file_upload(
    file_content: bytes,
    filename: str,
    ticker: str,
    upload_type: str = "broker_summary"  # or "financial_report"
) -> FileUploadResponse:
    """
    Handle file upload and parsing.
    
    Args:
        file_content: Raw file bytes
        filename: Original filename
        ticker: Stock ticker
        upload_type: "broker_summary" or "financial_report"
    
    Returns:
        FileUploadResponse with parsed data
    """
    file_type = validate_file_type(filename)
    errors = []
    warnings = []
    parsed_data = None
    
    if file_type == FileType.UNKNOWN:
        return FileUploadResponse(
            success=False,
            message="Unsupported file type. Please upload PDF, CSV, or Excel file.",
            file_type=file_type,
            file_name=filename,
            errors=["Unsupported file type"]
        )
    
    try:
        if upload_type == "broker_summary":
            if file_type == FileType.PDF:
                data = parse_broker_summary_pdf(file_content, ticker, filename)
            else:
                data = parse_broker_summary_csv(file_content, ticker, filename)
            parsed_data = data.model_dump()
            
        elif upload_type == "financial_report":
            if file_type == FileType.PDF:
                data = parse_financial_report_pdf(file_content, ticker, filename)
            else:
                data = parse_financial_report(file_content, ticker, filename, file_type)
            parsed_data = data.model_dump()
        
        else:
            errors.append(f"Unknown upload type: {upload_type}")
        
        # Add warnings for data quality
        if parsed_data:
            if upload_type == "broker_summary":
                if len(parsed_data.get("top_buyers", [])) < 3:
                    warnings.append("Less than 3 buyers found - BCR calculation may be inaccurate")
                if parsed_data.get("retail_disguise_detected"):
                    warnings.append("Retail disguise patterns detected - review carefully")
        
        return FileUploadResponse(
            success=True,
            message=f"Successfully parsed {upload_type.replace('_', ' ')} from {filename}",
            file_type=file_type,
            file_name=filename,
            parsed_data=parsed_data,
            warnings=warnings
        )
        
    except Exception as e:
        logger.error(f"Error processing upload: {e}")
        return FileUploadResponse(
            success=False,
            message=f"Failed to parse file: {str(e)}",
            file_type=file_type,
            file_name=filename,
            errors=[str(e)]
        )
