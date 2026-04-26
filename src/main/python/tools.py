import datetime
import statistics
from framework import BaseTool
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# --- 1. Ticker Validation ---
class TickerValidationTool(BaseTool):
    @property
    def name(self):
        return "validate_ticker"

    def get_declaration(self):
        return {"name": self.name, "description": "Validates a ticker.", 
                "parameters": {"type": "OBJECT", "properties": {"ticker": {"type": "STRING"}}, "required": ["ticker"]}}
    
    def _run_logic(self, context, ticker: str):
        data = context.get_fundamental_data(ticker)
        return "Valid" if data.get("quoteResponse", {}).get("result") else "Invalid"
    

