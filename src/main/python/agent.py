import os
import json
import datetime
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
    

