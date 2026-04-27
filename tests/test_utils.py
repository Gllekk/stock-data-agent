import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from stock_agent.agent import StockAgent


def mock_tool_call(name, args):
    mock_fn = MagicMock()
    mock_fn.name = name
    mock_fn.args = args
    mock_part = MagicMock(function_call=mock_fn, text=None)
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
    return mock_response

def mock_text_response(text):
    mock_part = MagicMock(function_call=None, text=text)
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]
    return mock_response


class BaseAgentTest(unittest.TestCase):
    def setUp(self):
        self.print_patcher = patch('builtins.print')
        self.mock_print = self.print_patcher.start()

        self.client_patcher = patch('stock_agent.agent.genai.Client')
        self.mock_client_class = self.client_patcher.start()

        self.agent = StockAgent("fake_api_key")

        self.patch_funds = patch.object(self.agent.registry, 'get_fundamental_data')
        self.patch_chart = patch.object(self.agent.registry, 'get_chart_data')
        self.patch_news = patch.object(self.agent.registry, 'get_news_xml')
        
        self.mock_funds = self.patch_funds.start()
        self.mock_chart = self.patch_chart.start()
        self.mock_news = self.patch_news.start()

        self.mock_funds.return_value = {
            "quoteResponse": {"result": [{"symbol": "MOCK", "marketCap": 5000000000, "trailingPE": 42.5}]}
        }
        
        dummy_prices = [100.0 + (i * 0.5) for i in range(60)]
        self.mock_chart.return_value = {
            "chart": {
                "result": [{
                    "meta": {"regularMarketPrice": 271.06, "currency": "USD"},
                    "indicators": {"quote": [{"close": dummy_prices}]}
                }]
            }
        }

        dummy_xml = "<rss><channel>" + ("<item><title>News - Default</title></item>" * 15) + "</channel></rss>"
        self.mock_news.return_value = dummy_xml

    def tearDown(self):
        self.patch_news.stop()
        self.patch_chart.stop()
        self.patch_funds.stop()
        self.client_patcher.stop()
        self.print_patcher.stop()