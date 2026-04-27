import os
import sys
import datetime
import statistics
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from stock_agent.framework import BaseTool



# --- 1. Ticker Validation Tool ---
class TickerValidationTool(BaseTool):
    @property
    def name(self) -> str:
        return "validate_ticker"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "MANDATORY FIRST STEP: Verifies if a stock ticker symbol is valid before any other analysis.",
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


# --- 6. News Sentiment Tool ---
class NewsSentimentTool(BaseTool):
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()

    @property
    def name(self) -> str:
        return "get_news_sentiment"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Performs NLP analysis on the latest 15 news headlines to determine sentiment.",
            "parameters": {"type": "OBJECT", "properties": {"ticker": {"type": "STRING"}}, "required": ["ticker"]}
        }

    def _run_logic(self, context, ticker: str):
        xml = context.get_news_xml(ticker)
        if "error" in xml: return xml
        
        items = xml.split("<item>")[1:16]
        headlines = [i.split("<title>")[1].split("</title>")[0].rsplit(" - ", 1)[0] for i in items]
        
        scores = [self.analyzer.polarity_scores(h)['compound'] for h in headlines]
        valid_scores = [s for s in scores if s != 0]
        avg = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        return {
            "sentiment": "Positive" if avg > 0.15 else "Negative" if avg < -0.15 else "Neutral",
            "nlp_score": round(avg, 3),
            "articles_analyzed": len(headlines)
        }


# --- 7. Risk Flags Tool ---
class RiskFlagsTool(BaseTool):
    @property
    def name(self) -> str:
        return "evaluate_risk"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Flags potential risks based on technical and fundamental data.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"tech": {"type": "OBJECT"}, "fund": {"type": "OBJECT"}},
                "required": ["tech", "fund"]
            }
        }

    def _run_logic(self, context, tech: dict, fund: dict):
        flags = []
        if tech.get('rsi', 50) > 70: flags.append("Overbought (RSI > 70)")
        if tech.get('rsi', 50) < 30: flags.append("Oversold (RSI < 30)")
        
        vol_str = tech.get('volatility', '0%').replace('%', '')
        if float(vol_str) > 40: flags.append("High Volatility (> 40%)")
        
        pe = fund.get('pe')
        if isinstance(pe, (int, float)) and pe > 50:
            flags.append(f"High Valuation (P/E: {pe})")
            
        return flags if flags else ["No high-risk flags identified."]


# --- 8. Calculate All Metrics Tool (Facade) ---
class CalculateAllMetricsTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_consolidated_report_data"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "FACADE: Collects all data points (Price, Techs, Fundamentals, Sentiment, Risks) in one call.",
            "parameters": {"type": "OBJECT", "properties": {"ticker": {"type": "STRING"}}, "required": ["ticker"]}
        }

    def _run_logic(self, context, ticker: str):
        # Using the internal _run_logic of other tools to assemble the report data
        price = CurrentPriceTool()._run_logic(context, ticker)
        techs = TechnicalIndicatorTool()._run_logic(context, ticker)
        funds = FundamentalsTool()._run_logic(context, ticker)
        news = NewsSentimentTool()._run_logic(context, ticker)
        risks = RiskFlagsTool()._run_logic(context, tech=techs, fund=funds)
        
        return {
            "ticker": ticker,
            "price_metrics": price,
            "technical_indicators": techs,
            "fundamental_data": funds,
            "sentiment_analysis": news,
            "risk_flags": risks
        }


# --- 9. Report Formatting Tool ---
class ReportFormattingTool(BaseTool):
    @property
    def name(self) -> str:
        return "format_final_report"

    def get_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": "Formats raw financial data into a human-readable CLI report.",
            "parameters": {"type": "OBJECT", "properties": {"data": {"type": "OBJECT"}}, "required": ["data"]}
        }

    def _run_logic(self, context, data: dict):
        try:
            ticker = data.get('ticker', 'N/A').upper()
            p = data.get('price_metrics', {})
            t = data.get('technical_indicators', {})
            f = data.get('fundamental_data', {})
            s = data.get('sentiment_analysis', {})
            r = data.get('risk_flags', [])

            report = f"""
==================================================
        FINANCIAL REPORT: {ticker}
==================================================
[MARKET STATUS]
* Price:          {p.get('price', 'N/A')} {p.get('currency', 'USD')}
* Market Cap:     {f.get('market_cap', 'N/A')}
* P/E Ratio:      {f.get('pe', 'N/A')}
* EPS:            {f.get('eps', 'N/A')}

[TECHNICAL ANALYSIS]
* RSI (14-Day):   {t.get('rsi', 'N/A')}
* SMA (50-Day):   {t.get('sma50', 'N/A')}
* MACD:           {t.get('macd', 'N/A')}
* Volatility:     {t.get('volatility', 'N/A')}
* Bollinger:      {t.get('bollinger', {}).get('lower', 'N/A')} - {t.get('bollinger', {}).get('upper', 'N/A')}

[SENTIMENT & NEWS]
* Tone:           {s.get('sentiment', 'N/A')}
* NLP Score:      {s.get('nlp_score', 'N/A')}
* Articles:       {s.get('articles_analyzed', 0)}

[RISK EVALUATION]
* {chr(10).join(['- ' + flag for flag in r])}
=================================================="""
            return report
        except Exception as e:
            return f"Error formatting report: {str(e)}"
    
