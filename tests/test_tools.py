import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from stock_agent.tools import (
    TickerValidationTool, CurrentPriceTool, ReportFormattingTool,
    SpecificDatePriceTool, TechnicalIndicatorTool, FundamentalsTool,
    NewsSentimentTool, RiskFlagsTool, CalculateAllMetricsTool
)


class TestTools(unittest.TestCase):
    def setUp(self):
        self.mock_context = MagicMock()

    def test_ticker_validation_tool_valid(self):
        self.mock_context.get_fundamental_data.return_value = {
            "quoteResponse": {"result": [{"symbol": "AAPL"}]}
        }
        tool = TickerValidationTool()
        result = tool._run_logic(self.mock_context, "AAPL")
        self.assertEqual(result, "Valid")

    def test_ticker_validation_tool_invalid(self):
        self.mock_context.get_fundamental_data.return_value = {
            "quoteResponse": {"result": []}
        }
        tool = TickerValidationTool()
        result = tool._run_logic(self.mock_context, "INVALID")
        self.assertEqual(result, "Invalid")

    def test_current_price_tool(self):
        self.mock_context.get_chart_data.return_value = {
            "chart": {
                "result": [{"meta": {"regularMarketPrice": 150.50, "currency": "USD"}}]
            }
        }
        tool = CurrentPriceTool()
        result = tool._run_logic(self.mock_context, "AAPL")
        self.assertEqual(result, {"price": 150.50, "currency": "USD"})

    def test_specific_date_price_tool(self):
        self.mock_context.get_historical_window.return_value = {
            "chart": {
                "result": [{"indicators": {"quote": [{"close": [145.25]}]}}]
            }
        }
        tool = SpecificDatePriceTool()
        result = tool._run_logic(self.mock_context, "AAPL", "2023-01-15")
        self.assertIn("145.25", result)

    def test_technical_indicator_tool_insufficient_data(self):
        self.mock_context.get_chart_data.return_value = {
            "chart": {"result": [{"indicators": {"quote": [{"close": [150.0, 151.0]}]}}]}
        }
        tool = TechnicalIndicatorTool()
        result = tool._run_logic(self.mock_context, "AAPL")
        self.assertEqual(result, "Insufficient data for technical analysis (need 50+ days).")

    def test_technical_indicator_tool_success(self):
        dummy_prices = [100.0 + i for i in range(60)]
        self.mock_context.get_chart_data.return_value = {
            "chart": {"result": [{"indicators": {"quote": [{"close": dummy_prices}]}}]}
        }
        tool = TechnicalIndicatorTool()
        result = tool._run_logic(self.mock_context, "AAPL")
        
        self.assertIn("sma50", result)
        self.assertIn("rsi", result)
        self.assertIn("macd", result)
        self.assertIn("bollinger", result)
        self.assertIn("volatility", result)
        self.assertIsInstance(result["bollinger"], dict)

    def test_fundamentals_tool(self):
        self.mock_context.get_fundamental_data.return_value = {
            "quoteResponse": {
                "result": [{
                    "marketCap": 2000000000,
                    "trailingPE": 25.5,
                    "trailingEps": 5.1,
                    "dividendYield": 0.015
                }]
            }
        }
        tool = FundamentalsTool()
        result = tool._run_logic(self.mock_context, "AAPL")
        
        self.assertEqual(result["market_cap"], 2000000000)
        self.assertEqual(result["pe"], 25.5)
        self.assertEqual(result["eps"], 5.1)
        self.assertEqual(result["div_yield"], "1.50%")

    def test_news_sentiment_tool(self):
        dummy_xml = "<rss><channel>"
        for i in range(5):
            dummy_xml += f"<item><title>Apple reports excellent earnings and great growth - News</title></item>"
        dummy_xml += "</channel></rss>"
        
        self.mock_context.get_news_xml.return_value = dummy_xml
        
        tool = NewsSentimentTool()
        result = tool._run_logic(self.mock_context, "AAPL")
        
        self.assertEqual(result["sentiment"], "Positive")
        self.assertTrue(result["nlp_score"] > 0)
        self.assertEqual(result["articles_analyzed"], 5)

    def test_risk_flags_tool_high_risk(self):
        tech_data = {"rsi": 85, "volatility": "55%"}
        fund_data = {"pe": 60} 
        
        tool = RiskFlagsTool()
        result = tool._run_logic(self.mock_context, tech=tech_data, fund=fund_data)
        
        self.assertEqual(len(result), 3)
        self.assertIn("Overbought (RSI > 70)", result)
        self.assertIn("High Volatility (> 40%)", result)
        self.assertIn("High Valuation (P/E: 60)", result)

    def test_risk_flags_tool_low_risk(self):
        tech_data = {"rsi": 50, "volatility": "20%"} 
        fund_data = {"pe": 15}                       
        
        tool = RiskFlagsTool()
        result = tool._run_logic(self.mock_context, tech=tech_data, fund=fund_data)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "No high-risk flags identified.")

    def test_calculate_all_metrics_tool(self):
        dummy_prices = [100.0 + i for i in range(60)]
        self.mock_context.get_chart_data.return_value = {
            "chart": {
                "result": [{
                    "meta": {"regularMarketPrice": 160.0, "currency": "USD"},
                    "indicators": {"quote": [{"close": dummy_prices}]}
                }]
            }
        }
        
        self.mock_context.get_fundamental_data.return_value = {
            "quoteResponse": {"result": [{"marketCap": 2000000000, "trailingPE": 25.5}]}
        }
        
        dummy_xml = "<rss><channel><item><title>Apple is doing fine - News</title></item></channel></rss>"
        self.mock_context.get_news_xml.return_value = dummy_xml

        tool = CalculateAllMetricsTool()
        result = tool._run_logic(self.mock_context, "AAPL")

        self.assertEqual(result["ticker"], "AAPL")
        self.assertIn("price_metrics", result)
        self.assertIn("technical_indicators", result)
        self.assertIn("fundamental_data", result)
        self.assertIn("sentiment_analysis", result)
        self.assertIn("risk_flags", result)
        
        # Spot check nested data
        self.assertEqual(result["price_metrics"]["price"], 160.0)
        self.assertEqual(result["fundamental_data"]["pe"], 25.5)

    def test_report_formatting_tool(self):
        tool = ReportFormattingTool()
        sample_data = {
            "ticker": "AAPL",
            "price_metrics": {"price": 150.0, "currency": "USD"},
            "fundamental_data": {"market_cap": "3T"},
            "risk_flags": ["High Volatility (> 40%)"]
        }
        result = tool._run_logic(self.mock_context, sample_data)
        self.assertIn("FINANCIAL REPORT: AAPL", result)
        self.assertIn("150.0 USD", result)
        self.assertIn("High Volatility", result)


if __name__ == '__main__':
    unittest.main()