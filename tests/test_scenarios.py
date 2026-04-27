import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tests.test_utils import BaseAgentTest, mock_tool_call, mock_text_response


class TestAgentScenarios(BaseAgentTest):
    def test_scenario_1_current_price(self):
        self.agent.client.models.generate_content.side_effect = [
            mock_tool_call("validate_ticker", {"ticker": "AAPL"}),
            mock_tool_call("get_current_price", {"ticker": "AAPL"}),
            mock_text_response("The current price of AAPL is $250.00 USD.")
        ]
        
        result = self.agent.run("What is the current price of AAPL?")
        
        self.assertEqual(result, "The current price of AAPL is $250.00 USD.")
        self.mock_funds.assert_called_with("AAPL")
        self.mock_chart.assert_called_with("AAPL", days=1)

    def test_scenario_2_rsi_indicator(self):
        self.agent.client.models.generate_content.side_effect = [
            mock_tool_call("validate_ticker", {"ticker": "MSFT"}),
            mock_tool_call("calculate_technicals", {"ticker": "MSFT"}),
            mock_text_response("The current RSI for MSFT is 75.00.")
        ]
        
        result = self.agent.run("What is the RSI for Microsoft?")
        
        self.assertEqual(result, "The current RSI for MSFT is 75.00.")
        self.mock_chart.assert_called_with("MSFT", days=100)

    def test_scenario_3_news_sentiment(self):
        # Setup LLM Multi-turn Mock
        self.agent.client.models.generate_content.side_effect = [
            mock_tool_call("validate_ticker", {"ticker": "RHM.DE"}),
            mock_tool_call("get_news_sentiment", {"ticker": "RHM.DE"}),
            mock_text_response("The current news sentiment for Rheinmetall (RHM.DE) is **Neutral**, based on an NLP analysis of the latest 15 headlines with a score of **0.0**.")
        ]
        
        result = self.agent.run("What is the sentiment around Rheinmetall?")
        
        self.assertIn("**Neutral**", result)
        self.mock_news.assert_called_with("RHM.DE")

    def test_scenario_4_full_report_with_fallback(self):
        dummy_report_data = {
            "ticker": "NVDA",
            "price_metrics": {"price": 210.00, "currency": "USD"},
            "technical_indicators": {
                "rsi": 87.00, 
                "sma50": 185.00, 
                "macd": 12.00, 
                "volatility": "36.00%",
                "bollinger": {"lower": 160.00, "upper": 215.00}
            },
            "fundamental_data": {
                "market_cap": "5,000,000,000,000", 
                "pe": 43.00, 
                "eps": "N/A"
            },
            "sentiment_analysis": {
                "sentiment": "Positive", 
                "nlp_score": 0.40, 
                "articles_analyzed": 15
            },
            "risk_flags": ["Overbought (RSI > 70)"]
        }
        
        final_answer = """
==================================================
        FINANCIAL REPORT: NVDA
==================================================
[MARKET STATUS]
* Price:          210.00 USD
* Market Cap:     5,000,000,000,000
* P/E Ratio:      43.00
* EPS:            N/A

[TECHNICAL ANALYSIS]
* RSI (14-Day):   87.00
* SMA (50-Day):   185.00
* MACD:           12.00
* Volatility:     36.00%
* Bollinger:      160.00 - 215.00

[SENTIMENT & NEWS]
* Tone:           Positive
* NLP Score:      0.40
* Articles:       15

[RISK EVALUATION]
* - Overbought (RSI > 70)
=================================================="""

        self.agent.client.models.generate_content.side_effect = [
            Exception("429 Quota/Demand issue"),                                    
            mock_tool_call("validate_ticker", {"ticker": "NVDA"}),                  
            mock_tool_call("get_consolidated_report_data", {"ticker": "NVDA"}),     
            mock_tool_call("format_final_report", {"data": dummy_report_data}),     
            mock_text_response(final_answer)                                        
        ]
        
        result = self.agent.run("Give me a full report on Nvidia.")
        
        self.assertEqual(self.agent.current_model_idx, 1)
        self.assertEqual(result.strip(), final_answer.strip())
        
        self.mock_funds.assert_called_with("NVDA")
        self.mock_news.assert_called_with("NVDA")


    def test_clear_history(self):
        self.agent.history = ["some", "past", "context"]
        self.agent.current_model_idx = 2
        
        self.agent.clear_history()
        
        self.assertEqual(len(self.agent.history), 0)
        self.assertEqual(self.agent.current_model_idx, 0)

if __name__ == '__main__':
    unittest.main()