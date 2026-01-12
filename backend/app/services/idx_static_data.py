"""
IDX Static Data - Pre-loaded company and broker data from IDX website

Uses cached JSON files from idx-bei library for fast search.
Does NOT require network requests - works offline.

Data:
- 956 Indonesian companies (emitens) - includes BUMI and other Yahoo-missing stocks
- 93 registered brokers/securities firms

Usage:
    from app.services.idx_static_data import search_emitens, get_all_brokers
    
    results = search_emitens("BUMI")  # Search by code or name
    brokers = get_all_brokers()  # Get all 93 brokers
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from functools import lru_cache
import re

# Path to idx-bei data directory
IDX_DATA_DIR = Path(__file__).parent.parent.parent.parent / "broker" / "data"


# ==================== DATA LOADING ====================

@lru_cache(maxsize=1)
def load_all_companies() -> List[Dict]:
    """
    Load all 956 companies from allCompanies.json
    
    Returns list of companies with:
    - KodeEmiten: Stock code (e.g., 'BUMI', 'BBCA')
    - NamaEmiten: Company name
    - Sektor: Sector
    - SubSektor: Sub-sector
    - Industri: Industry
    - TanggalPencatatan: Listing date
    - Website, Email, Telepon, etc.
    """
    json_path = IDX_DATA_DIR / "allCompanies.json"
    
    if not json_path.exists():
        print(f"[IDX-STATIC] Warning: {json_path} not found")
        return []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        companies = data.get("data", [])
        print(f"[IDX-STATIC] Loaded {len(companies)} companies")
        return companies
        
    except Exception as e:
        print(f"[IDX-STATIC] Error loading companies: {e}")
        return []


@lru_cache(maxsize=1)
def load_all_brokers() -> List[Dict]:
    """
    Load all 93 brokers from brokerSearch.json
    
    Returns list of brokers with:
    - Code: Broker code (e.g., 'XC', 'YP')
    - Name: Company name (e.g., 'AJAIB SEKURITAS ASIA')
    - License: License types
    """
    json_path = IDX_DATA_DIR / "brokerSearch.json"
    
    if not json_path.exists():
        print(f"[IDX-STATIC] Warning: {json_path} not found")
        return []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        brokers = data.get("data", [])
        print(f"[IDX-STATIC] Loaded {len(brokers)} brokers")
        return brokers
        
    except Exception as e:
        print(f"[IDX-STATIC] Error loading brokers: {e}")
        return []


# ==================== SEARCH FUNCTIONS ====================

def search_emitens(query: str, limit: int = 20) -> List[Dict]:
    """
    Search emitens (companies) by code or name.
    
    Searches across:
    - KodeEmiten (stock code)
    - NamaEmiten (company name)
    
    Args:
        query: Search query (case insensitive)
        limit: Maximum results to return
    
    Returns:
        List of matching companies formatted for frontend
    
    Example:
        search_emitens("BUMI") -> [{"symbol": "BUMI", "name": "PT Bumi Resources Tbk", ...}]
        search_emitens("bank") -> [{"symbol": "BBCA", "name": "Bank Central Asia Tbk", ...}]
    """
    if not query or len(query) < 1:
        return []
    
    query = query.upper().strip()
    companies = load_all_companies()
    
    results = []
    exact_matches = []
    starts_with = []
    contains = []
    
    for company in companies:
        code = company.get("KodeEmiten", "").upper()
        name = company.get("NamaEmiten", "").upper()
        
        # Exact match on code (highest priority)
        if code == query:
            exact_matches.append(company)
        # Code starts with query
        elif code.startswith(query):
            starts_with.append(company)
        # Code or name contains query
        elif query in code or query in name:
            contains.append(company)
    
    # Combine results by priority
    all_matches = exact_matches + starts_with + contains
    
    # Format for frontend
    for company in all_matches[:limit]:
        results.append({
            "symbol": company.get("KodeEmiten", ""),
            "name": company.get("NamaEmiten", ""),
            "sector": company.get("Sektor", ""),
            "subsector": company.get("SubSektor", ""),
            "industry": company.get("Industri", ""),
            "listing_date": company.get("TanggalPencatatan", ""),
            "board": company.get("PapanPencatatan", ""),
            "website": company.get("Website", ""),
            "source": "idx"
        })
    
    return results


def get_company_by_code(code: str) -> Optional[Dict]:
    """
    Get single company by exact code.
    
    Args:
        code: Stock code (e.g., 'BUMI')
    
    Returns:
        Company dict or None if not found
    """
    code = code.upper().replace(".JK", "")
    companies = load_all_companies()
    
    for company in companies:
        if company.get("KodeEmiten", "").upper() == code:
            return {
                "symbol": company.get("KodeEmiten", ""),
                "name": company.get("NamaEmiten", ""),
                "sector": company.get("Sektor", ""),
                "subsector": company.get("SubSektor", ""),
                "industry": company.get("Industri", ""),
                "subindustry": company.get("SubIndustri", ""),
                "listing_date": company.get("TanggalPencatatan", ""),
                "board": company.get("PapanPencatatan", ""),
                "address": company.get("Alamat", ""),
                "website": company.get("Website", ""),
                "email": company.get("Email", ""),
                "phone": company.get("Telepon", ""),
                "fax": company.get("Fax", ""),
                "logo": f"https://www.idx.co.id{company.get('Logo', '')}",
                "source": "idx"
            }
    
    return None


# ==================== BROKER CLASSIFICATION DATA ====================
# Hardcoded classification to avoid API dependency.
# Sources: Market knowledge, Stockbit tags, historical behavior.

BROKER_CLASSIFICATION = {
    # RETAIL (Online Trading dominant)
    "YP": {"type": "RETAIL", "is_foreign": False, "name_short": "Mirae"},
    "PD": {"type": "RETAIL", "is_foreign": False, "name_short": "IPOT"},
    "CC": {"type": "RETAIL", "is_foreign": False, "name_short": "Mandiri"},
    "NI": {"type": "RETAIL", "is_foreign": False, "name_short": "BNI"},
    "XC": {"type": "RETAIL", "is_foreign": False, "name_short": "Ajaib"},
    "XL": {"type": "RETAIL", "is_foreign": False, "name_short": "Stockbit"},
    "GR": {"type": "RETAIL", "is_foreign": False, "name_short": "Panin"},
    "KK": {"type": "RETAIL", "is_foreign": False, "name_short": "Phillip"},
    "EP": {"type": "RETAIL", "is_foreign": False, "name_short": "MNC"},
    "OD": {"type": "RETAIL", "is_foreign": False, "name_short": "Danamon"},
    "SQ": {"type": "RETAIL", "is_foreign": False, "name_short": "BCA"},
    
    # FOREIGN INSTITUTION (Big Funds)
    "ZP": {"type": "INSTITUTION", "is_foreign": True, "name_short": "Maybank"},
    "MS": {"type": "INSTITUTION", "is_foreign": True, "name_short": "Morgan Stanley"},
    "KZ": {"type": "INSTITUTION", "is_foreign": True, "name_short": "CLSA"},
    "CS": {"type": "INSTITUTION", "is_foreign": True, "name_short": "Credit Suisse"},
    "AK": {"type": "INSTITUTION", "is_foreign": True, "name_short": "UBS"},
    "BK": {"type": "INSTITUTION", "is_foreign": True, "name_short": "JP Morgan"},
    "RX": {"type": "INSTITUTION", "is_foreign": True, "name_short": "Macquarie"},
    "CG": {"type": "INSTITUTION", "is_foreign": True, "name_short": "Citigroup"},
    "AG": {"type": "INSTITUTION", "is_foreign": True, "name_short": "Kiwoom"},
    
    # DOMESTIC INSTITUTION / BIG PLAYER
    "YU": {"type": "INSTITUTION", "is_foreign": False, "name_short": "CIMB"},
    "DX": {"type": "INSTITUTION", "is_foreign": False, "name_short": "Bahana"},
    "CP": {"type": "INSTITUTION", "is_foreign": False, "name_short": "Valbury"},
    "AI": {"type": "INSTITUTION", "is_foreign": False, "name_short": "UOB"},
    "MG": {"type": "INSTITUTION", "is_foreign": False, "name_short": "Semesta"}, # Scalper King
    "LG": {"type": "INSTITUTION", "is_foreign": False, "name_short": "Trimegah"},
    "RF": {"type": "INSTITUTION", "is_foreign": False, "name_short": "Buana"},
    "AZ": {"type": "INSTITUTION", "is_foreign": False, "name_short": "Sucor"},
    "DR": {"type": "INSTITUTION", "is_foreign": False, "name_short": "RHB"},
}

def get_all_brokers() -> List[Dict]:
    """
    Get all 93 registered brokers with ENRICHED classification.
    
    Returns:
        List of brokers with code, name, license, type, is_foreign
    """
    brokers = load_all_brokers()
    results = []
    
    for b in brokers:
        code = b.get("Code", "")
        
        # Default values
        b_type = "UNKNOWN" 
        is_foreign = False
        
        # Enriched values
        if code in BROKER_CLASSIFICATION:
            info = BROKER_CLASSIFICATION[code]
            b_type = info["type"]
            is_foreign = info["is_foreign"]
        
        results.append({
            "code": code,
            "name": b.get("Name", ""),
            "license": b.get("License", ""),
            "type": b_type,
            "is_foreign": is_foreign,
            "source": "idx"
        })
        
    return results


def search_brokers(query: str, limit: int = 20) -> List[Dict]:
    """
    Search brokers by code or name.
    
    Args:
        query: Search query
        limit: Max results
    """
    if not query:
        return get_all_brokers()[:limit]
    
    query = query.upper().strip()
    brokers = load_all_brokers()
    
    results = []
    for broker in brokers:
        code = broker.get("Code", "").upper()
        name = broker.get("Name", "").upper()
        
        if query in code or query in name:
            results.append({
                "code": broker.get("Code", ""),
                "name": broker.get("Name", ""),
                "license": broker.get("License", ""),
                "source": "idx"
            })
            
            if len(results) >= limit:
                break
    
    return results


def get_broker_by_code(code: str) -> Optional[Dict]:
    """
    Get broker by exact code.
    
    Args:
        code: Broker code (e.g., 'XC', 'YP')
    """
    code = code.upper()
    brokers = load_all_brokers()
    
    for broker in brokers:
        if broker.get("Code", "").upper() == code:
            b_code = broker.get("Code", "")
            
            # Default values
            b_type = "UNKNOWN"
            is_foreign = False
            
            # Enriched values
            if b_code in BROKER_CLASSIFICATION:
                info = BROKER_CLASSIFICATION[b_code]
                b_type = info["type"]
                is_foreign = info["is_foreign"]

            return {
                "code": b_code,
                "name": broker.get("Name", ""),
                "license": broker.get("License", ""),
                "type": b_type,
                "is_foreign": is_foreign,
                "source": "idx"
            }
    
    # If not found in loaded brokers (or file missing), check hardcoded classification
    if code in BROKER_CLASSIFICATION:
        info = BROKER_CLASSIFICATION[code]
        return {
            "code": code,
            "name": info.get("name_short", code),
            "license": "Unknown",
            "type": info["type"],
            "is_foreign": info["is_foreign"],
            "source": "static_fallback"
        }
    
    return None


# ==================== STATISTICS ====================

def get_data_stats() -> Dict:
    """Get statistics about loaded data"""
    companies = load_all_companies()
    brokers = load_all_brokers()
    
    # Count by sector
    sectors = {}
    for c in companies:
        sector = c.get("Sektor", "Unknown")
        sectors[sector] = sectors.get(sector, 0) + 1
    
    return {
        "total_companies": len(companies),
        "total_brokers": len(brokers),
        "sectors": sectors,
        "data_source": str(IDX_DATA_DIR)
    }


# ==================== TESTING ====================

if __name__ == "__main__":
    print("\n=== Testing IDX Static Data ===\n")
    
    # Test loading
    stats = get_data_stats()
    print(f"Companies: {stats['total_companies']}")
    print(f"Brokers: {stats['total_brokers']}")
    
    # Test BUMI search
    print("\n1. Search 'BUMI':")
    results = search_emitens("BUMI")
    for r in results[:3]:
        print(f"   {r['symbol']} - {r['name']}")
    
    # Test bank search
    print("\n2. Search 'BANK':")
    results = search_emitens("BANK")
    for r in results[:5]:
        print(f"   {r['symbol']} - {r['name']}")
    
    # Test get company
    print("\n3. Get BUMI details:")
    bumi = get_company_by_code("BUMI")
    if bumi:
        print(f"   Name: {bumi['name']}")
        print(f"   Sector: {bumi['sector']}")
        print(f"   Industry: {bumi['industry']}")
    
    print("\n=== Test Complete ===")
