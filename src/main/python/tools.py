import datetime
import statistics
from framework import BaseTool
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# --- 1. Ticker Validation Tool ---
class TickerValidationTool(BaseTool):
    @property
    def name(self) -> str:
        return "validate_ticker"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Verifies if a stock ticker symbol is valid.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"ticker": {"type": "STRING", "description": "Ticker symbol (e.g., AAPL)"}},
                "required": ["ticker"]
            }
        }

    def _run_logic(self, context, ticker: str):
        data = context.get_fundamental_data(ticker)
        res = data.get("quoteResponse", {}).get("result", [])
        return "Valid" if len(res) > 0 else "Invalid"
    

# --- 2. Current Price Tool ---
class CurrentPriceTool(BaseTool):
    @property
    def name(self) -> str: return "get_current_price"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Fetches the current trading price and currency of a stock.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"ticker": {"type": "STRING"}},
                "required": ["ticker"]
            }
        }

    def _run_logic(self, context, ticker: str):
        data = context.get_chart_data(ticker, days=1)
        if "error" in data: return data["error"]
        
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        currency = meta.get("currency", "USD")
        
        if price is None: return f"Could not retrieve price for {ticker}."
        return {"price": price, "currency": currency}