import os
import json
import datetime
import urllib.request
import urllib.parse
from google import genai
from google.genai import types
from framework import AgentObserver, Colors
import tools


# Helper for handling network I/O
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

