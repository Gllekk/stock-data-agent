# Stock Data Agent

A CLI-based stock analysis application powered by an AI agent. The system accepts natural language queries about publicly traded stocks and responds with either a concise answer or a fully formatted multi-metric report, depending on what the user asks for. All financial data is retrieved in real time from Yahoo Finance and Google News.

---

## Features

- **Natural language interface** — ask questions about stocks in plain English, with or without knowing the ticker symbol
- **Live data retrieval** — current price, historical closing prices, fundamental metrics, and recent news fetched at query time
- **Technical analysis** — 50-day SMA, 14-day RSI, MACD, 20-day Bollinger Bands, and annualised volatility calculated from raw price series
- **News sentiment scoring** — the 15 most recent headlines for a given stock are scored using VADER NLP and aggregated into a Positive / Neutral / Negative label
- **Risk flagging** — overbought/oversold RSI, high volatility, and elevated P/E ratio are surfaced automatically
- **Full consolidated report** — a single command generates a structured, human-readable report covering all of the above metrics
- **Input validation** — every query is screened for emptiness, gibberish, invalid characters, profanity, and prompt injection before reaching the model
- **Automatic model fallback** — if the active Gemini model hits a quota or availability limit, the agent silently switches to the next model in the fallback list and retries
- **Data caching** — chart data, fundamentals, and news XML are cached within a session to avoid redundant HTTP requests

---

## Project Structure

```
stock-data-agent/
├── src/
│   └── stock_agent/
│       ├── __init__.py
│       ├── agent.py           # StockAgent, ToolRegistry, ToolHelper — ReAct loop and orchestration
│       ├── framework.py       # BaseTool, AgentObserver, ConsoleLogger, Colors — shared abstractions
│       ├── tools.py           # All nine tool implementations
│       ├── validator.py       # InputValidator — multi-layer input screening
│       └── main.py            # CLI entry point
├── tests/
│   ├── __init__.py
│   ├── test_utils.py          # BaseAgentTest, mock_tool_call, mock_text_response — shared test infrastructure
│   ├── test_validator.py      # InputValidator unit tests
│   ├── test_tools.py          # Individual tool unit tests
│   ├── test_scenarios.py      # End-to-end agent scenario tests
│   └── test_error_handling.py # API error and fallback tests
├── docs/
│   ├── Code_Components.md     # Full reference for all modules, classes, and methods
│   ├── Data.md                # Data sources, schemas, and retrieval details
│   ├── Deployment.md          # Installation, configuration, and deployment guide
│   └── Testing.md             # Test suite reference and coverage breakdown
├── .gitignore
└── pyproject.toml
```

---

## Prerequisites


| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.10+ | Required for `tuple[bool, str]` type hint syntax used in `validator.py` |
| pip | Any recent version | Used to install project dependencies |
| Git | Any version | Required to clone the repository |
| Google Gemini API Key | — | Obtainable from [Google AI Studio](https://aistudio.google.com/app/apikey) |

Internet access is required at runtime for live data retrieval.

---

## Installation

**1. Clone the repository:**

```
git clone <repository-url>
cd stock-data-agent
```


**2. Install all dependencies:**

```
pip install google-genai vaderSentiment pyspellchecker better-profanity pytest
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `google-genai` | Google Gemini SDK — model inference and tool-call parsing |
| `vaderSentiment` | Rule-based NLP sentiment scoring for news headlines |
| `pyspellchecker` | English dictionary lookup used in the gibberish detection check |
| `better-profanity` | Profanity and obfuscated language detection |
| `pytest` | Test discovery and execution *(development only)* |

---

## Configuration

The application requires one environment variable to be set before starting:

### `GEMINI_API_KEY`

A valid API key for the Google Gemini API. The application exits immediately at startup if this variable is not present.

**macOS / Linux:**
```
export GEMINI_API_KEY="your_api_key_here"
```

**Windows (Command Prompt):**
```
set GEMINI_API_KEY=your_api_key_here
```

**Windows (PowerShell):**
```
$env:GEMINI_API_KEY="your_api_key_here"
```

To avoid setting this on every new session, add the export line to your shell profile (e.g., `~/.zshrc` or `~/.bashrc`).

> **Note:** Ensure the key has access to at least the primary model in the fallback list. The configured sequence is `gemini-3.1-flash-lite-preview` → `gemini-3-flash-preview` → `gemini-2.5-flash` → `gemini-2.5-flash-lite`. This list can be edited in `StockAgent.__init__` inside `agent.py`.

---

## Usage

Start the application from the **project root directory**:

```
python src/stock_agent/main.py
```

A successful startup prints the following banner:

```
--- Stock Analysis System Initialized ---
Commands: 'exit' or 'quit' to quit
          'clear' to reset history

[USER] Ask about a stock:
```

### System Commands

| Input | Action |
|---|---|
| `exit` or `quit` | Shuts down the application |
| `clear` | Resets conversation history, clears all data caches, and resets the active model to the primary one |
| `Ctrl+C` | Interrupts and exits gracefully at any point |

### Example Queries

```
What is the current price of AAPL?
What was Tesla's closing price on 2024-03-15?
Give me the RSI and Bollinger Bands for MSFT.
What are the fundamentals for Amazon?
What is the sentiment around Rheinmetall?
Give me a full report on Nvidia.
TSLA
```

### Console Output

| Colour | Prefix | Meaning |
|---|---|---|
| Cyan | `[USER]` | Input prompt |
| Magenta | `[AGENT]` | Tool invocations and the final answer |
| Yellow | `[SYSTEM]` | Raw output returned by each tool |
| Red | `[ERROR]` | Validation failures, API errors, or unexpected exceptions |

### Full Report Format

When asked for a full report, the agent produces output in the following structure:

```
==================================================
        FINANCIAL REPORT: AAPL
==================================================
[MARKET STATUS]
* Price:          191.45 USD
* Market Cap:     2950000000000
* P/E Ratio:      31.2
* EPS:            6.13

[TECHNICAL ANALYSIS]
* RSI (14-Day):   58.34
* SMA (50-Day):   183.71
* MACD:           2.1043
* Volatility:     22.47%
* Bollinger:      174.22 - 198.60

[SENTIMENT & NEWS]
* Tone:           Positive
* NLP Score:      0.241
* Articles:       15

[RISK EVALUATION]
* - No high-risk flags identified.
==================================================
```

---

## Available Tools

The agent selects from nine tools at runtime based on the user's query:

| Tool | Description |
|---|---|
| `validate_ticker` | Mandatory first call — verifies the ticker is valid before any other tool is invoked |
| `get_current_price` | Fetches the live market price and trading currency |
| `get_price_on_date` | Retrieves the closing price for a specific past date |
| `calculate_technicals` | Calculates SMA50, RSI, MACD, Bollinger Bands, and annualised volatility |
| `get_fundamentals` | Fetches market cap, trailing P/E, trailing EPS, and dividend yield |
| `get_news_sentiment` | Scores the 15 most recent headlines with VADER and returns a sentiment label |
| `evaluate_risk` | Flags overbought/oversold RSI, high volatility, and elevated P/E |
| `get_consolidated_report_data` | Facade — invokes all data tools and aggregates results into one dictionary |
| `format_final_report` | Formats the aggregated dictionary into the structured CLI report |

---

## Running the Tests

The test suite requires no API key and makes no real network or API calls — all external dependencies are mocked.

Run all tests from the project root:

```
pytest
```

Run with verbose output:

```
pytest -v
```

Run a specific module:

```
pytest tests/test_tools.py
```

All 29 tests should pass. For a full breakdown of the test suite, see `Testing.md`.

---

