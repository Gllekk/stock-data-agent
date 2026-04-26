import json
import datetime
from typing import List
import urllib.request
import urllib.parse
from google import genai
from google.genai import types
from framework import AgentObserver, Colors
import tools


# Helper for StockAgent infrastructure to handle network I/O
class ToolHelper:
    _cookie = None
    _crumb = None

    @staticmethod
    def _init_yahoo_session():
        if ToolHelper._crumb: return
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        try:
            req = urllib.request.Request('https://fc.yahoo.com', headers=headers)
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            cookie_header = e.headers.get('Set-Cookie')
            if cookie_header: ToolHelper._cookie = cookie_header.split(';')[0]
        except Exception: pass

        if ToolHelper._cookie:
            try:
                headers['Cookie'] = ToolHelper._cookie
                req = urllib.request.Request('https://query1.finance.yahoo.com/v1/test/getcrumb', headers=headers)
                with urllib.request.urlopen(req, timeout=10) as r:
                    ToolHelper._crumb = r.read().decode()
            except Exception: pass

    @staticmethod
    def _get_request(url: str):
        ToolHelper._init_yahoo_session()
        if ToolHelper._crumb and "yahoo.com" in url:
            url += ("&" if "?" in url else "?") + f"crumb={ToolHelper._crumb}"
        
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, text/xml'}
        if ToolHelper._cookie and "yahoo.com" in url:
            headers['Cookie'] = ToolHelper._cookie
        return urllib.request.Request(url, headers=headers)

    @staticmethod
    def fetch_json(url: str):
        req = ToolHelper._get_request(url)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())

    @staticmethod
    def fetch_text(url: str):
        req = ToolHelper._get_request(url)
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode()


# Tool registry for managing tools
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.cache_chart = {}
        self.cache_funds = {}
        self.cache_news = {}

    def add(self, tool): self.tools[tool.name] = tool

    def get_chart_data(self, ticker: str, days: int = 7):
        key = f"{ticker}_{days}"
        if key not in self.cache_chart:
            end = int(datetime.datetime.now().timestamp())
            start = end - (days * 86400)
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start}&period2={end}&interval=1d"
            self.cache_chart[key] = ToolHelper.fetch_json(url)
        return self.cache_chart[key]

    def get_historical_window(self, ticker: str, start: int, end: int):
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start}&period2={end}&interval=1d"
        return ToolHelper.fetch_json(url)

    def get_fundamental_data(self, ticker: str):
        if ticker not in self.cache_funds:
            url = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
            self.cache_funds[ticker] = ToolHelper.fetch_json(url)
        return self.cache_funds[ticker]

    def get_news_xml(self, ticker: str):
        if ticker not in self.cache_news:
            safe_ticker = urllib.parse.quote(ticker)
            url = f"https://news.google.com/rss/search?q={safe_ticker}+stock&hl=en-US"
            self.cache_news[ticker] = ToolHelper.fetch_text(url)
        return self.cache_news[ticker]

    def run(self, name, args):
        if name not in self.tools: return f"Error: Tool {name} not found."
        return self.tools[name].execute(self, **args)
    

class StockAgent:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.registry = ToolRegistry()
        self.history = []
        self.observers: List[AgentObserver] = []
        
        # Fallback list for automatic model switching
        self.available_models = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite"]
        self.current_model_idx = 0
        
        self._init_tools()

    def _init_tools(self):
        tool_classes = []
        for tc in tool_classes:
            self.registry.add(tc())

    # Clear conversational context to save quota/tokens 
    def clear_history(self):
        self.history.clear()
        self.registry.cache.clear()

    def run(self, prompt: str):
        self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        while True:
            try:
                # Attempt API Call
                response = self.client.models.generate_content(
                    model=self.available_models[self.current_model_idx],
                    contents=self.history,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(function_declarations=[t.get_declaration() for t in self.registry.tools.values()])],
                        system_instruction=(
                            "You are a strict, factual financial data agent.\n"
                            f"1. CRITICAL: Today's date is {current_date}. Base all your temporal logic (past vs. future) on this date.\n"
                            "2. CRITICAL: NEVER invent, simulate, or guess financial data, tool arguments, or metrics. \n"
                            "3. If a data-fetching tool returns an error (like a network error or 401), STOP immediately. Inform the user of the error and do NOT attempt to call downstream tools (like evaluate_risk or format_final_report) with made-up data.\n"
                            "4. For simple questions, use the specific tool needed (e.g., get_current_price for price). Use get_consolidated_report_data ONLY for full report requests."
                        )
                    )
                )
            except Exception as e:
                # Exception Handling: Quota & Demand Fallbacks
                error_msg = str(e).lower()
                if any(err in error_msg for err in ["429", "503", "quota", "exhausted", "overloaded"]):
                    if self.current_model_idx < len(self.available_models) - 1:
                        self.current_model_idx += 1
                        print(f"{Colors.ERROR}[SYSTEM ERROR] Quota/Demand issue. Auto-switching to model: {self.available_models[self.current_model_idx]}{Colors.RESET}")
                        continue # Retry loop with the new model
                    else:
                        return f"Critical Error: All fallback models exhausted. Original issue: {str(e)}"
                return f"API Error: {str(e)}"

            model_content = response.candidates[0].content
            self.history.append(model_content)
            
            # Process Tool Calls and Final Answers
            if model_content.parts and model_content.parts[0].function_call:
                fn = model_content.parts[0].function_call
                for o in self.observers: o.update("ACT", {"name": fn.name, "args": fn.args})
                
                result = self.registry.run(fn.name, fn.args)
                
                for o in self.observers: o.update("OBSERVE", result)
                self.history.append(types.Content(
                    role="user", 
                    parts=[types.Part.from_function_response(name=fn.name, response={"result": result})]
                ))
            else:
                final_text = model_content.parts[0].text
                for o in self.observers: o.update("FINAL", final_text)
                return final_text