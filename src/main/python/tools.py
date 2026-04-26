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
    def name(self) -> str:
        return "get_current_price"

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
    

# --- 3. Specific Date Price Tool ---
class SpecificDatePriceTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_price_on_date"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Retrieves the closing price of a stock on a specific past date.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "ticker": {"type": "STRING"},
                    "date": {"type": "STRING", "description": "YYYY-MM-DD format"}
                },
                "required": ["ticker", "date"]
            }
        }

    def _run_logic(self, context, ticker: str, date: str):
        try:
            target_dt = datetime.datetime.strptime(date, "%Y-%m-%d")
            p1 = int(target_dt.timestamp())
            p2 = int((target_dt + datetime.timedelta(days=1)).timestamp())
            
            data = context.get_historical_window(ticker, p1, p2)
            if "error" in data: return data["error"]
            
            res = data.get("chart", {}).get("result", [{}])[0]
            prices = [p for p in res.get("indicators", {}).get("quote", [{}])[0].get("close", []) if p is not None]
            
            if not prices: return f"No trading data found for {ticker} on {date}."
            return f"Closing price for {ticker} on {date}: {prices[0]:.2f}"
        except Exception as e:
            return f"Error parsing date or fetching data: {str(e)}"


# --- 4. Technical Indicators Tool (SMA, RSI, MACD, Bollinger, Volatility) ---
class TechnicalIndicatorTool(BaseTool):
    @property
    def name(self) -> str:
        return "calculate_technicals"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Calculates 5 key indicators: SMA50, RSI, MACD, Bollinger Bands, and Annual Volatility.",
            "parameters": {"type": "OBJECT", "properties": {"ticker": {"type": "STRING"}}, "required": ["ticker"]}
        }

    def _run_logic(self, context, ticker: str):
        data = context.get_chart_data(ticker, days=100)
        if "error" in data: return data["error"]
        
        res = data.get("chart", {}).get("result", [{}])[0]
        prices = [p for p in res.get("indicators", {}).get("quote", [{}])[0].get("close", []) if p is not None]
        
        if len(prices) < 50: return "Insufficient data for technical analysis (need 50+ days)."

        # SMA 50
        sma50 = sum(prices[-50:]) / 50
        
        # RSI 14
        diffs = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d for d in diffs[-14:] if d > 0]
        losses = [abs(d) for d in diffs[-14:] if d < 0]
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 0.001
        rsi = 100 - (100 / (1 + (avg_gain/avg_loss)))
        
        # MACD (12-26 Proxy)
        macd = (sum(prices[-12:]) / 12) - (sum(prices[-26:]) / 26)
        
        # Bollinger Bands (20-day)
        sma20 = sum(prices[-20:]) / 20
        std20 = statistics.stdev(prices[-20:])
        
        # Annualized Volatility
        returns = [(prices[i]/prices[i-1]) - 1 for i in range(1, len(prices))]
        vol = statistics.stdev(returns) * (252 ** 0.5)

        return {
            "sma50": round(sma50, 2),
            "rsi": round(rsi, 2),
            "macd": round(macd, 4),
            "bollinger": {"upper": round(sma20 + 2*std20, 2), "lower": round(sma20 - 2*std20, 2)},
            "volatility": f"{vol:.2%}"
        }


# --- 5. Fundamentals Tool ---
class FundamentalsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_fundamentals"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Retrieves Market Cap, P/E Ratio, EPS, and Dividend Yield.",
            "parameters": {"type": "OBJECT", "properties": {"ticker": {"type": "STRING"}}, "required": ["ticker"]}
        }

    def _run_logic(self, context, ticker: str):
        data = context.get_fundamental_data(ticker)
        if "error" in data: return data["error"]
        
        res = data.get("quoteResponse", {}).get("result", [{}])[0]
        return {
            "market_cap": res.get("marketCap", "N/A"),
            "pe": res.get("trailingPE", "N/A"),
            "eps": res.get("trailingEps", "N/A"),
            "div_yield": f"{res.get('dividendYield', 0):.2%}" if res.get('dividendYield') else "0.00%"
        }



