
import yfinance as yf
import pandas as pd
from app.models.schemas import MarketData
from typing import Optional

class MarketDataService:
    def get_market_data(self, ticker: str) -> Optional[MarketData]:
        try:
            # Add .JK suffix if missing (for Indonesia Stock Exchange)
            yf_ticker = ticker.upper()
            if not yf_ticker.endswith(".JK"):
                yf_ticker += ".JK"
            
            stock = yf.Ticker(yf_ticker)
            
            # Fetch 1 year of data for chart
            hist = stock.history(period="1y")
            
            if hist.empty:
                print(f"No data found for {yf_ticker}")
                return None
                
            current_price = hist['Close'].iloc[-1]
            
            # Helper to format candles for lightweight-charts
            # lightweight-charts wants { time: 1678900000, open: 100, high: 105, low: 98, close: 102 }
            candles = []
            for index, row in hist.iterrows():
                candles.append({
                    "time": int(index.timestamp()),
                    "open": float(row['Open']),
                    "high": float(row['High']),
                    "low": float(row['Low']),
                    "close": float(row['Close'])
                })
            
            # Convert to list of dicts for Pydantic model
            
            return MarketData(
                ticker=ticker,
                price=current_price,
                pe_ratio=stock.info.get('trailingPE', 0.0),
                pb_ratio=stock.info.get('priceToBook', 0.0),
                market_cap=stock.info.get('marketCap', 0),
                volume=stock.info.get('volume', 0),
                historical_prices=candles,
                # Required fields by schema (defaults for now)
                free_float_ratio=0.5,
                fol=1.0,
                atr=0.0,
                macd=0.0,
                volatility=0.02
            )
            
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None
