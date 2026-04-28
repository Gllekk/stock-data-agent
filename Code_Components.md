# Code Components — Stock Data Agent

A technical reference for all modules, classes, methods, and tools implemented across the `stock_agent` package.

---

## Table of Contents

1. [framework.py](#1-frameworkpy)
2. [agent.py](#2-agentpy)
3. [tools.py](#3-toolspy)
4. [validator.py](#4-validatorpy)
5. [main.py](#5-mainpy)

---

## 1. `framework.py`

Defines the foundational abstractions and shared utilities used across the entire package. All core base classes and display constants live here.

---

### Class: `Colors`

A static container of ANSI escape code constants used to apply colour formatting to CLI output. No instantiation is required; all attributes are accessed directly on the class.

| Attribute | Value | Purpose |
|---|---|---|
| `USER` | `'\033[96m'` | Cyan — used for user input labels |
| `AGENT` | `'\033[95m'` | Magenta — used for agent output labels |
| `SYSTEM` | `'\033[93m'` | Yellow — used for system/observer messages |
| `ERROR` | `'\033[91m'` | Red — used for error messages |
| `RESET` | `'\033[0m'` | Resets terminal colour to default |

---

### Abstract Class: `AgentObserver`

An abstract base class (ABC) that defines the observer interface for monitoring agent lifecycle events. Concrete subclasses must implement the `update` method.

#### Method: `update(event_type, data)` *(abstract)*

The callback invoked by the agent whenever a notable event occurs.

| Parameter | Type | Description |
|---|---|---|
| `event_type` | `str` | A string token identifying the event. Expected values: `"ACT"`, `"OBSERVE"`, `"FINAL"` |
| `data` | `Any` | The payload associated with the event — a dict for `"ACT"`, raw tool output for `"OBSERVE"`, and a string for `"FINAL"` |

---

### Class: `ConsoleLogger(AgentObserver)`

A concrete implementation of `AgentObserver` that prints formatted, colour-coded agent activity to standard output.

#### Method: `_truncate(text, max_length=100)`

A private helper that sanitises and shortens a string for single-line console display.

| Parameter | Type | Description |
|---|---|---|
| `text` | `str` | The string to process |
| `max_length` | `int` | Maximum character length before truncation. Defaults to `100` |

Returns the cleaned string, appending `"..."` if the original exceeded `max_length`.

#### Method: `update(event_type, data)`

Handles the three recognised event types and writes formatted output to the console.

| `event_type` | Behaviour |
|---|---|
| `"ACT"` | Prints a truncated summary of the tool name and arguments being invoked |
| `"OBSERVE"` | Prints a truncated summary of the tool's raw output |
| `"FINAL"` | Prints the agent's complete, untruncated final answer |

---

### Abstract Class: `BaseTool`

An abstract base class that all tool implementations must extend. Establishes a uniform interface for tool metadata, declaration generation, and safe execution.

#### Abstract Property: `name`

Returns the unique string identifier for the tool. Used as a key in the `ToolRegistry` and must match the name declared in `get_declaration()`.

#### Abstract Method: `get_declaration()`

Returns a dictionary conforming to the Google GenAI function declaration schema. This declaration is passed to the model to describe the tool's name, purpose, and parameter schema.

#### Method: `execute(registry_context, **kwargs)`

The public entry point for running a tool. Wraps `_run_logic` in a `try/except` block to ensure that any unhandled exception is caught and returned as a formatted error string rather than propagating upward.

| Parameter | Type | Description |
|---|---|---|
| `registry_context` | `ToolRegistry` | The shared registry instance, providing access to cached data-fetching methods |
| `**kwargs` | `Any` | Keyword arguments matching the tool's declared parameter schema |

Returns the result of `_run_logic`, or an `"Execution Error in {name}: ..."` string on failure.

#### Abstract Method: `_run_logic(context, **kwargs)`

Contains the tool's core business logic. Must be implemented by every concrete tool subclass.

---

## 2. `agent.py`

Implements the runtime infrastructure: network I/O helpers, the tool registry, and the main agent loop that orchestrates model calls and tool execution.

---

### Class: `ToolHelper`

A static utility class that manages low-level HTTP requests and Yahoo Finance session state (cookie and crumb authentication). All methods and attributes are static; the class is never instantiated.

#### Class Attributes

| Attribute | Type | Description |
|---|---|---|
| `_cookie` | `str \| None` | Session cookie retrieved from `fc.yahoo.com`, required for authenticated Yahoo Finance requests |
| `_crumb` | `str \| None` | Anti-CSRF crumb token required by Yahoo Finance query endpoints |

#### Static Method: `_init_yahoo_session()`

Initialises the Yahoo Finance session by fetching a session cookie from `fc.yahoo.com` and subsequently exchanging it for a crumb token from the Yahoo Finance crumb endpoint. No-ops if `_crumb` is already populated. Called automatically before every Yahoo Finance request.

#### Static Method: `_get_request(url)`

Constructs a `urllib.request.Request` object with the appropriate headers (`User-Agent`, `Accept`, `Cookie`) and appends the crumb token as a query parameter for Yahoo Finance URLs.

| Parameter | Type | Description |
|---|---|---|
| `url` | `str` | The target URL |

Returns a configured `urllib.request.Request` instance.

#### Static Method: `fetch_json(url)`

Executes the request built by `_get_request` and deserialises the response body as JSON.

| Parameter | Type | Description |
|---|---|---|
| `url` | `str` | The target URL |

Returns a parsed Python `dict`.

#### Static Method: `fetch_text(url)`

Executes the request built by `_get_request` and returns the raw response body as a decoded string. Used for fetching RSS/XML feeds.

| Parameter | Type | Description |
|---|---|---|
| `url` | `str` | The target URL |

Returns a `str`.

---

### Class: `ToolRegistry`

Manages the collection of available tools and provides a shared, cached data-access layer that tools use to retrieve financial data without making redundant network calls.

#### Attributes

| Attribute | Type | Description |
|---|---|---|
| `tools` | `dict` | Maps tool name strings to their `BaseTool` instances |
| `cache_chart` | `dict` | Caches chart/price data keyed by `"{ticker}_{days}"` |
| `cache_funds` | `dict` | Caches fundamental quote data keyed by ticker symbol |
| `cache_news` | `dict` | Caches raw RSS XML keyed by ticker symbol |

#### Method: `add(tool)`

Registers a `BaseTool` instance into the `tools` dict using the tool's `name` property as the key.

#### Method: `clear_all_caches()`

Empties all three caches (`cache_chart`, `cache_funds`, `cache_news`), forcing fresh network requests on the next data access.

#### Method: `get_chart_data(ticker, days=7)`

Fetches and caches OHLCV chart data from the Yahoo Finance chart endpoint for a trailing window of `days` calendar days at daily resolution.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | Stock ticker symbol |
| `days` | `int` | Number of trailing days to fetch. Defaults to `7` |

Returns the parsed JSON response dict.

#### Method: `get_historical_window(ticker, start, end)`

Fetches chart data for an explicit Unix timestamp range. Results are **not** cached, as this method is used for arbitrary point-in-time lookups.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | Stock ticker symbol |
| `start` | `int` | Start of the window as a Unix timestamp |
| `end` | `int` | End of the window as a Unix timestamp |

Returns the parsed JSON response dict.

#### Method: `get_fundamental_data(ticker)`

Fetches and caches quote summary data (market cap, P/E, EPS, etc.) from the Yahoo Finance quote endpoint.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | Stock ticker symbol |

Returns the parsed JSON response dict.

#### Method: `get_news_xml(ticker)`

Fetches and caches the Google News RSS feed for a given ticker's stock-related articles.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | Stock ticker symbol |

Returns the raw XML response as a `str`.

#### Method: `run(name, args)`

Looks up a tool by name and delegates execution to its `execute` method.

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | The registered tool name |
| `args` | `dict` | Keyword arguments to pass to the tool |

Returns the tool's output, or an `"Error: Tool {name} not found."` string if the name is not registered.

---

### Class: `StockAgent`

The top-level agent that drives the model–tool loop. Manages conversation history, model selection, and the agentic reasoning cycle.

#### Constructor: `__init__(api_key)`

Initialises the Google GenAI client, an empty `ToolRegistry`, an empty conversation history list, and an empty observers list. Calls `_init_tools()` to populate the registry and sets the model fallback list and current model index.

| Parameter | Type | Description |
|---|---|---|
| `api_key` | `str` | A valid Google Gemini API key |

#### Attributes

| Attribute | Type | Description |
|---|---|---|
| `client` | `genai.Client` | The initialised Google GenAI client |
| `registry` | `ToolRegistry` | The shared tool registry and data cache |
| `history` | `list[types.Content]` | The accumulated multi-turn conversation history |
| `observers` | `list[AgentObserver]` | Registered observer instances that receive lifecycle events |
| `available_models` | `list[str]` | Ordered list of model identifiers used for automatic quota-based fallback |
| `current_model_idx` | `int` | Index into `available_models` pointing to the currently active model |

#### Method: `_init_tools()`

Instantiates each tool class defined in `tools.py` and registers them with `self.registry`. The tool classes registered are: `TickerValidationTool`, `CurrentPriceTool`, `SpecificDatePriceTool`, `TechnicalIndicatorTool`, `FundamentalsTool`, `NewsSentimentTool`, `RiskFlagsTool`, `CalculateAllMetricsTool`, and `ReportFormattingTool`.

#### Method: `clear_history()`

Resets the conversation to a clean state by clearing `self.history`, all registry caches, and resetting the active model index to `0`.

#### Method: `run(prompt)`

Executes the core agentic loop for a given user prompt. Appends the prompt to history, then enters a `while True` loop that alternates between model inference and tool execution until the model produces a text-only response (the final answer).

**Model call behaviour:** Passes the full conversation history and all tool declarations to the active Gemini model along with a system instruction enforcing strict factual behaviour.

**Quota/demand fallback:** If the API raises a `429`, `503`, quota-exhausted, or overloaded error, the method increments `current_model_idx` and retries with the next model in `available_models`. If all fallback models are exhausted, a critical error string is returned.

**Tool execution branch:** When the model responds with a `function_call`, the method:
1. Notifies all observers with an `"ACT"` event.
2. Dispatches the call to `registry.run()`.
3. Notifies all observers with an `"OBSERVE"` event.
4. Checks the result string for `"Error"` or `"Invalid"`. If found, notifies observers with a `"FINAL"` event and returns immediately without continuing the loop.
5. Otherwise, appends the tool result to history as a `function_response` and iterates.

**Final answer branch:** When the model responds with plain text, notifies observers with a `"FINAL"` event and returns the text.

| Parameter | Type | Description |
|---|---|---|
| `prompt` | `str` | The validated user query to process |

Returns the agent's final answer as a `str`, or an error message string if a critical failure occurred.

---

## 3. `tools.py`

Contains all nine concrete `BaseTool` implementations. Each tool is self-contained: it declares its own schema, handles its own data extraction, and returns either a structured dict or a plain string.

---

### Class: `TickerValidationTool`

**Tool name:** `validate_ticker`

Verifies that a given ticker symbol corresponds to a real, tradeable security. This is the mandatory first tool called for every stock query.

#### Method: `_run_logic(context, ticker)`

Calls `context.get_fundamental_data(ticker)` and checks whether the `quoteResponse.result` list is non-empty.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | The ticker symbol to validate |

Returns `"Valid"` if the ticker resolves to a known security, or `"Invalid"` otherwise.

---

### Class: `CurrentPriceTool`

**Tool name:** `get_current_price`

Retrieves the most recent market price and the trading currency for a stock.

#### Method: `_run_logic(context, ticker)`

Calls `context.get_chart_data(ticker, days=1)` and extracts the `regularMarketPrice` and `currency` fields from the chart metadata.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | The ticker symbol |

Returns a dict with keys `price` (`float`) and `currency` (`str`), or an error string if the price cannot be retrieved.

---

### Class: `SpecificDatePriceTool`

**Tool name:** `get_price_on_date`

Retrieves the closing price of a stock on a specific historical date.

#### Method: `_run_logic(context, ticker, date)`

Parses `date` into Unix timestamps for a one-day window, calls `context.get_historical_window()`, and extracts the first non-null closing price from the result.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | The ticker symbol |
| `date` | `str` | Target date in `YYYY-MM-DD` format |

Returns a formatted string `"Closing price for {ticker} on {date}: {price:.2f}"`, a `"No trading data found"` message if the market was closed on that date, or an error string on parse/fetch failure.

---

### Class: `TechnicalIndicatorTool`

**Tool name:** `calculate_technicals`

Computes five standard technical indicators from the trailing 100 days of daily closing prices.

#### Method: `_run_logic(context, ticker)`

Fetches 100 days of chart data and calculates the following indicators from the closing price series:

| Indicator | Calculation Method |
|---|---|
| **SMA 50** | Simple average of the last 50 closing prices |
| **RSI 14** | Standard 14-period Relative Strength Index using average gain/loss of the last 14 daily differences |
| **MACD** | Difference between the 12-period and 26-period simple moving averages (proxy calculation) |
| **Bollinger Bands** | 20-period SMA ± 2 standard deviations |
| **Annual Volatility** | Standard deviation of daily returns scaled by √252 |

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | The ticker symbol |

Returns a dict with keys `sma50`, `rsi`, `macd`, `bollinger` (a nested dict with `upper` and `lower`), and `volatility` (a percentage string). Returns an insufficiency message if fewer than 50 data points are available.

---

### Class: `FundamentalsTool`

**Tool name:** `get_fundamentals`

Retrieves core fundamental valuation metrics for a stock.

#### Method: `_run_logic(context, ticker)`

Calls `context.get_fundamental_data(ticker)` and extracts four fields from the first result in `quoteResponse.result`.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | The ticker symbol |

Returns a dict with keys `market_cap`, `pe` (trailing P/E ratio), `eps` (trailing EPS), and `div_yield` (formatted as a percentage string).

---

### Class: `NewsSentimentTool`

**Tool name:** `get_news_sentiment`

Performs NLP-based sentiment analysis on the most recent news headlines for a stock.

#### Constructor: `__init__()`

Initialises a `vaderSentiment.SentimentIntensityAnalyzer` instance stored as `self.analyzer`.

#### Method: `_run_logic(context, ticker)`

Fetches the Google News RSS feed via `context.get_news_xml(ticker)`, parses up to 15 `<item>` elements, extracts the `<title>` text from each, and strips the publication source suffix. Computes the VADER compound score for each headline, filters out neutral zeros, and averages the remainder.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | The ticker symbol |

Returns a dict with keys:

| Key | Type | Description |
|---|---|---|
| `sentiment` | `str` | `"Positive"` if average score > 0.15, `"Negative"` if < -0.15, otherwise `"Neutral"` |
| `nlp_score` | `float` | The average VADER compound score rounded to 3 decimal places |
| `articles_analyzed` | `int` | The number of headlines processed |

---

### Class: `RiskFlagsTool`

**Tool name:** `evaluate_risk`

Identifies potential risk conditions by inspecting pre-computed technical and fundamental data.

#### Method: `_run_logic(context, tech, fund)`

Evaluates four risk conditions against the provided data dicts:

| Condition | Threshold | Flag Text |
|---|---|---|
| Overbought | RSI > 70 | `"Overbought (RSI > 70)"` |
| Oversold | RSI < 30 | `"Oversold (RSI < 30)"` |
| High Volatility | Volatility > 40% | `"High Volatility (> 40%)"` |
| High Valuation | P/E > 50 | `"High Valuation (P/E: {pe})"` |

| Parameter | Type | Description |
|---|---|---|
| `tech` | `dict` | Output dict from `TechnicalIndicatorTool` |
| `fund` | `dict` | Output dict from `FundamentalsTool` |

Returns a list of flag strings, or `["No high-risk flags identified."]` if no thresholds were breached.

---

### Class: `CalculateAllMetricsTool`

**Tool name:** `get_consolidated_report_data`

A facade tool that aggregates the outputs of all five data-gathering tools into a single structured payload in one agent step.

#### Method: `_run_logic(context, ticker)`

Directly calls the `_run_logic` methods of `CurrentPriceTool`, `TechnicalIndicatorTool`, `FundamentalsTool`, `NewsSentimentTool`, and `RiskFlagsTool` in sequence, passing the technical and fundamental results into the risk tool.

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | The ticker symbol |

Returns a dict with keys `ticker`, `price_metrics`, `technical_indicators`, `fundamental_data`, `sentiment_analysis`, and `risk_flags`.

---

### Class: `ReportFormattingTool`

**Tool name:** `format_final_report`

Transforms the consolidated data payload into a human-readable, fixed-width CLI report string.

#### Method: `_run_logic(context, data)`

Unpacks the five sections of the `data` dict and assembles a multi-line report with four labelled sections: `[MARKET STATUS]`, `[TECHNICAL ANALYSIS]`, `[SENTIMENT & NEWS]`, and `[RISK EVALUATION]`.

| Parameter | Type | Description |
|---|---|---|
| `data` | `dict` | The output dict produced by `CalculateAllMetricsTool` |

Returns the formatted report as a multi-line `str`, or an `"Error formatting report: ..."` string on failure.

---

## 4. `validator.py`

Provides client-side input sanitisation before a user query is passed to the agent. All validation logic is encapsulated in a single class.

---

### Class: `InputValidator`

Applies a sequential pipeline of validation checks to raw user input, rejecting queries that are empty, too long, gibberish, contain invalid characters, include profanity, or appear to be prompt injection attempts.

#### Constructor: `__init__()`

Initialises the following components:

| Attribute | Type | Description |
|---|---|---|
| `injection_signatures` | `list[str]` | Hard-coded list of lowercase prompt injection substrings to check against |
| `spell` | `SpellChecker` | A `pyspellchecker` instance used for English dictionary lookups |

Also calls `profanity.load_censor_words()` to initialise the `better_profanity` filter.

#### Method: `_is_meaningful(user_input)`

Determines whether the input contains a sufficient proportion of recognisable English words to be considered a legitimate query rather than gibberish.

**Logic:**
1. Extracts all alphabetic tokens using a regex.
2. Filters out all-uppercase words (likely ticker symbols) and single-character words, treating the remainder as "standard words".
3. If no standard words remain but alphabetic tokens exist (i.e., the user typed only a ticker), returns `True`.
4. Checks how many standard words are recognised by `pyspellchecker`.
5. Returns `True` only if at least one word is known **and** the ratio of known-to-standard words is ≥ 0.40.

| Parameter | Type | Description |
|---|---|---|
| `user_input` | `str` | The raw input string to evaluate |

Returns `bool`.

#### Method: `validate(user_input)`

Runs the full validation pipeline in order. Returns on the first failing check.

| Check | Condition | Error Message Returned |
|---|---|---|
| Empty | `user_input` is blank after stripping | `"Input cannot be empty."` |
| Length | Length > 200 characters | `"Input is too long. Please keep your query under 200 characters."` |
| Gibberish | `_is_meaningful()` returns `False` | `"Input appears meaningless or contains too much gibberish..."` |
| Character set | Does not match `^[a-zA-Z0-9\s\.\,\?\'\"\-\:\$\%\&]+$` | `"Input contains invalid special characters..."` |
| Profanity | `profanity.contains_profanity()` returns `True` | `"Inappropriate language detected (including obfuscated text)."` |
| Prompt injection | Any `injection_signatures` entry found in lowercased input | `"Prompt injection attempt detected. Request blocked."` |

| Parameter | Type | Description |
|---|---|---|
| `user_input` | `str` | The raw input string to validate |

Returns a `tuple[bool, str]`: `(True, "")` if all checks pass, or `(False, "<error message>")` on the first failure.

---

## 5. `main.py`

The application entry point. Responsible for bootstrapping the agent and running the interactive CLI session.

---

### Function: `main()`

Initialises the agent and runs the interactive read–validate–execute loop until the user exits.

**Startup sequence:**
1. Reads `GEMINI_API_KEY` from the environment and exits with an error if it is not set.
2. Instantiates `StockAgent` and registers a `ConsoleLogger` observer.
3. Instantiates `InputValidator`.
4. Prints a startup banner with available commands.

**Loop behaviour:** On each iteration, reads a line of input from stdin and processes it as follows:

| Input | Action |
|---|---|
| `"exit"` or `"quit"` | Prints a shutdown message and breaks the loop |
| `"clear"` | Calls `agent.clear_history()` and prints a confirmation |
| Any other input | Runs `validator.validate()`; if invalid, prints the error and continues; if valid, calls `agent.run(query)` |

**Error handling:** A `KeyboardInterrupt` (Ctrl+C) at any point gracefully prints a shutdown message and breaks the loop. Any other unhandled exception in the loop body is caught, printed, and the loop continues.
