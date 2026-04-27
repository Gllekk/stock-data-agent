import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tests.test_utils import BaseAgentTest, mock_tool_call, mock_text_response

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from stock_agent.framework import AgentObserver


class MockObserver(AgentObserver):
    def __init__(self):
        self.final_messages = []

    def update(self, event_type, data):
        if event_type == "FINAL":
            self.final_messages.append(data)

class TestErrorHandling(BaseAgentTest):
    def test_model_fallback_exhaustion(self):
        self.agent.client.models.generate_content.side_effect = Exception("429 Quota exhausted")
        result = self.agent.run("Analyze AAPL")
        
        self.assertEqual(self.agent.current_model_idx, len(self.agent.available_models) - 1)
        self.assertIn("Critical Error: all fallback models exhausted", result)

    def test_successful_model_fallback_recovery(self):
        mock_success_text = "Analysis complete: AAPL looks stable."
        
        self.agent.client.models.generate_content.side_effect = [
            Exception("503 Service Overloaded"), 
            mock_text_response(mock_success_text) # Using the shared helper!
        ]
        
        result = self.agent.run("Analyze AAPL")
        self.assertEqual(self.agent.current_model_idx, 1)
        self.assertEqual(result, mock_success_text)

    def test_standard_api_error_no_fallback(self):
        self.agent.client.models.generate_content.side_effect = Exception("400 Bad Request")
        result = self.agent.run("Analyze AAPL")
        
        self.assertEqual(self.agent.current_model_idx, 0)
        self.assertIn("api error", result.lower())

    def test_critical_tool_failure_halts_execution(self):
        observer = MockObserver()
        self.agent.observers.append(observer)
        
        self.agent.client.models.generate_content.return_value = mock_tool_call("validate_ticker", {"ticker": "FAKE"})
        self.agent.registry.run = MagicMock(return_value="Error: Ticker INVALID")
        
        result = self.agent.run("Check FAKE stock")
        
        self.assertIn("A required step failed", result)
        self.assertIn("Error: Ticker INVALID", result)

    def test_tool_internal_python_exception_handling(self):
        self.agent.client.models.generate_content.return_value = mock_tool_call(
            "validate_ticker", {"ticker": "AAPL"}
        )
        
        tool = self.agent.registry.tools["validate_ticker"]
        tool._run_logic = MagicMock(side_effect=ValueError("Simulated network crash"))
        
        result = self.agent.run("Analyze AAPL")

        self.assertIn("A required step failed", result)
        self.assertIn("Execution Error in validate_ticker", result)

if __name__ == '__main__':
    unittest.main()