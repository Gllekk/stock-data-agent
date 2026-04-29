# Data — Stock Data Agent

A technical reference describing every data retrieval, transformation, conversion, aggregation, and serialisation operation performed across the `stock_agent` package. Sections are organised by the nature of the data operation rather than by module, to reflect the actual flow of data through the system.

---

## Table of Contents

1. [External Data Retrieval](#1-external-data-retrieval)
2. [In-Memory Caching](#2-in-memory-caching)
3. [Data Extraction & Parsing](#3-data-extraction--parsing)
4. [Type Conversions](#4-type-conversions)
5. [Statistical & Financial Computations](#5-statistical--financial-computations)
6. [Threshold Evaluation & Risk Classification](#6-threshold-evaluation--risk-classification)
7. [Data Aggregation](#7-data-aggregation)
8. [Conversation State Management](#8-conversation-state-management)
9. [Tool Declaration Serialisation](#9-tool-declaration-serialisation)
10. [Input Sanitisation Pipeline](#10-input-sanitisation-pipeline)
11. [Output Formatting](#11-output-formatting)

---

## 1. External Data Retrieval

All outbound network calls originate in `ToolHelper` and `ToolRegistry` (`agent.py`). Three distinct external sources are used.

### 1.1 Yahoo Finance Session Authentication

Before any Yahoo Finance endpoint can be queried, a two-step session handshake must be completed. This is managed by `ToolHelper._init_yahoo_session()` and the state is held in two class-level variables.

**Step 1 — Cookie acquisition:**  
An HTTP request is made to `https://fc.yahoo.com`. Yahoo Finance intentionally responds with an `HTTPError`. The `Set-Cookie` header of that error response is intercepted and the first directive (everything before the first `;`) is extracted and stored as `ToolHelper._cookie`.

**Step 2 — Crumb token acquisition:**  
A second request is made to `https://query1.finance.yahoo.com/v1/test/getcrumb`, this time including the extracted cookie in the request headers. The plain-text body of the response is stored verbatim as `ToolHelper._crumb`.

Once both values are populated the method becomes a no-op on subsequent calls, so authentication happens at most once per process lifetime.

**Crumb injection:**  
Every subsequent Yahoo Finance URL is modified by `ToolHelper._get_request()` before being dispatched. If the URL already contains a query string (`?`), the crumb is appended with `&crumb=<value>`; otherwise it is appended with `?crumb=<value>`. The cookie is simultaneously injected as a request header.

### 1.2 Yahoo Finance Chart API (OHLCV Data)

**Endpoint:** `https://query2.finance.yahoo.com/v8/finance/chart/{ticker}`

**Query parameters used:**

| Parameter | Source | Description |
|---|---|---|
| `period1` | Computed Unix timestamp | Start of the requested time window |
| `period2` | Computed Unix timestamp | End of the requested time window (current time or day boundary) |
| `interval` | Hard-coded `1d` | Daily resolution for all requests |
| `crumb` | `ToolHelper._crumb` | Injected automatically by `_get_request()` |

This endpoint is called in two distinct modes:

- **Trailing window** (`ToolRegistry.get_chart_data`): `period2` is set to the current Unix timestamp and `period1` is derived by subtracting `days × 86400` seconds. Used by `CurrentPriceTool` (1 day), `TechnicalIndicatorTool` (100 days), and `CalculateAllMetricsTool`.
- **Explicit window** (`ToolRegistry.get_historical_window`): `period1` and `period2` are passed in directly as pre-computed Unix timestamps. Used exclusively by `SpecificDatePriceTool` for point-in-time lookups.

The raw response is a JSON object. Its binary body is decoded to a UTF-8 string and deserialised via `json.loads()` by `ToolHelper.fetch_json()`.

### 1.3 Yahoo Finance Quote API (Fundamental Data)

**Endpoint:** `https://query2.finance.yahoo.com/v7/finance/quote?symbols={ticker}`

Called by `ToolRegistry.get_fundamental_data()`. Returns a JSON object containing a `quoteResponse.result` array where each element is a flat dict of quote fields. The same response object is shared by both `TickerValidationTool` (which checks only for the presence of results) and `FundamentalsTool` (which extracts specific fields), avoiding a duplicate network call through caching.

### 1.4 Google News RSS Feed

**Endpoint:** `https://news.google.com/rss/search?q={safe_ticker}+stock&hl=en-US`

Called by `ToolRegistry.get_news_xml()`. The ticker symbol is first percent-encoded via `urllib.parse.quote()` to handle symbols that contain special characters (e.g. `BRK.B` → `BRK.B`). The query is suffixed with the literal string `+stock` to scope results. The response is an XML document retrieved as raw bytes, decoded to a UTF-8 string, and stored as-is. No XML library is used; all subsequent parsing is done through string operations in `NewsSentimentTool`.

---

## 2. In-Memory Caching

`ToolRegistry` maintains three `dict` objects that act as a request-scoped cache, eliminating redundant network calls when multiple tools query the same ticker within a single conversation turn.

| Cache dict | Key format | Stores | Populated by |
|---|---|---|---|
| `cache_chart` | `"{ticker}_{days}"` | Parsed JSON chart response | `get_chart_data()` |
| `cache_funds` | `"{ticker}"` | Parsed JSON quote response | `get_fundamental_data()` |
| `cache_news` | `"{ticker}"` | Raw RSS XML string | `get_news_xml()` |

**Cache hit behaviour:** Before making a network call, each accessor method checks whether the computed key is already present in the relevant dict. If it is, the cached value is returned immediately.

**Cache miss behaviour:** The network call is made, the result is stored under the computed key, and then returned.

**Non-cached retrieval:** `get_historical_window()` deliberately does not cache its results. Because it is parameterised by arbitrary `start`/`end` timestamps rather than a fixed day-count, a cache keyed only on ticker would be incorrect; keying on timestamps would produce unbounded cache growth for repeated point-in-time queries.

**Cache invalidation:** All three caches are cleared together by `ToolRegistry.clear_all_caches()`, which calls `.clear()` on each dict. This is triggered by `StockAgent.clear_history()` when the user issues the `clear` command, ensuring that a new conversation always fetches fresh market data.

---

## 3. Data Extraction & Parsing

### 3.1 JSON Response Traversal

All Yahoo Finance endpoints return deeply nested JSON. Each tool navigates to its required fields using chained `.get()` calls with fallback defaults, avoiding `KeyError` exceptions on missing or malformed responses.

**Chart response structure navigated:**

```
chart
  └── result[0]
        ├── meta
        │     ├── regularMarketPrice   → CurrentPriceTool
        │     └── currency             → CurrentPriceTool
        └── indicators
              └── quote[0]
                    └── close[]        → SpecificDatePriceTool, TechnicalIndicatorTool
```

The `close` array may contain `None` values where the market was closed (weekends, holidays). These are filtered out by a list comprehension (`[p for p in ... if p is not None]`) before any computation is performed.

**Quote response structure navigated:**

```
quoteResponse
  └── result[0]
        ├── (presence check only)       → TickerValidationTool
        ├── marketCap                   → FundamentalsTool
        ├── trailingPE                  → FundamentalsTool
        ├── trailingEps                 → FundamentalsTool
        └── dividendYield               → FundamentalsTool
```

### 3.2 RSS/XML String Parsing

`NewsSentimentTool._run_logic()` parses the raw RSS XML string without a dedicated XML parser. The process has three sequential string operations:

**Step 1 — Item extraction:** The XML string is split on the literal delimiter `"<item>"`. The first element of the resulting list (everything before the first article) is discarded via slice `[1:16]`, yielding at most 15 article segments.

**Step 2 — Title extraction:** For each segment, the content between the first `<title>` and `</title>` tags is extracted using a two-step string split: `split("<title>")[1].split("</title>")[0]`.

**Step 3 — Source suffix stripping:** Google News titles append the publisher name after a ` - ` separator (e.g., `"Apple reports record profits - Reuters"`). The publisher suffix is stripped using `rsplit(" - ", 1)[0]`, which splits from the right at most once, leaving the headline text intact even if it contains its own ` - ` sequences.

---

## 4. Type Conversions

### 4.1 Date String → `datetime` → Unix Timestamps

Performed in `SpecificDatePriceTool._run_logic()`.

1. The `date` argument (a `str` in `YYYY-MM-DD` format) is parsed into a `datetime.datetime` object via `datetime.datetime.strptime(date, "%Y-%m-%d")`.
2. `period1` is computed as `int(target_dt.timestamp())` — the Unix timestamp of midnight on the target date.
3. `period2` is computed as `int((target_dt + datetime.timedelta(days=1)).timestamp())` — the Unix timestamp of midnight on the following day, creating a 24-hour window that captures the day's single trading entry.

### 4.2 `datetime.now()` → Unix Timestamp

Performed in `ToolRegistry.get_chart_data()`.

`datetime.datetime.now().timestamp()` returns a `float`. It is cast to `int` via `int(...)` to produce a whole-second Unix timestamp suitable for use as a URL query parameter.

### 4.3 `datetime.now()` → Formatted Date String

Performed in `StockAgent.run()`.

`datetime.datetime.now().strftime("%Y-%m-%d")` produces a `YYYY-MM-DD` string that is embedded directly into the model's system instruction to inform it of the current date.

### 4.4 Ticker Symbol → URL-Encoded String

Performed in `ToolRegistry.get_news_xml()`.

`urllib.parse.quote(ticker)` percent-encodes any characters in the ticker that are not safe for inclusion in a URL query string. This is a defensive conversion for tickers that contain dots or slashes (e.g. `BRK.B`).

### 4.5 Raw Bytes → UTF-8 String

Performed in both `ToolHelper.fetch_json()` and `ToolHelper.fetch_text()`.

The HTTP response body is read as a `bytes` object via `r.read()`. Calling `.decode()` (which defaults to UTF-8) converts it to a Python `str`. In `fetch_json()`, the string is then immediately passed to `json.loads()` for deserialisation.

### 4.6 Dividend Yield Raw Float → Percentage String

Performed in `FundamentalsTool._run_logic()`.

`dividendYield` is returned by the API as a raw decimal fraction (e.g. `0.0052`). It is formatted as a human-readable percentage string using the `:.2%` format specifier, which multiplies by 100 and appends `%` (e.g. `"0.52%"`). If `dividendYield` is absent or falsy, the literal fallback `"0.00%"` is used.

### 4.7 Annualized Volatility Float → Percentage String

Performed in `TechnicalIndicatorTool._run_logic()`.

The computed annualized volatility is a plain `float` (e.g. `0.2847`). It is converted to a percentage string using the `:.2%` format specifier (e.g. `"28.47%"`) and stored as the `volatility` value in the returned dict.

### 4.8 Volatility Percentage String → Float

Performed in `RiskFlagsTool._run_logic()`.

The `volatility` field from the technical indicators dict is received as a percentage string (e.g. `"28.47%"`). The `%` character is stripped using `.replace('%', '')`, and the result is cast to `float` via `float(vol_str)` to enable numerical threshold comparison against the hard-coded limit of `40`.

### 4.9 Tool Result → String (Error Detection)

Performed in `StockAgent.run()`.

After every tool call, the raw result (which may be a `dict`, `list`, or `str`) is unconditionally cast to a string via `str(result)`. This normalised string is then inspected with `"Error" in res_str or "Invalid" in res_str` to determine whether the tool reported a failure, regardless of the original return type.

---

## 5. Statistical & Financial Computations

All computations are performed in `TechnicalIndicatorTool._run_logic()` on a `list[float]` of daily closing prices, with `None` values pre-filtered. The list may contain up to 100 elements (100 days of daily data). A minimum of 50 valid prices is required; the tool returns early with an error string if this threshold is not met.

### 5.1 50-Day Simple Moving Average (SMA 50)

The last 50 elements of the price list are sliced (`prices[-50:]`), summed, and divided by 50. The result is rounded to 2 decimal places.

### 5.2 14-Period Relative Strength Index (RSI 14)

1. **Daily differences** are computed for each consecutive pair in the full price list: `prices[i] - prices[i-1]`.
2. The last 14 differences are taken and partitioned into **gains** (positive differences) and **losses** (absolute values of negative differences).
3. Average gain and average loss are each computed as the sum divided by 14 (not divided by the count of gains/losses, preserving the standard RSI denominator). If there are no losses, `avg_loss` is set to `0.001` to avoid division by zero.
4. RSI is computed as `100 - (100 / (1 + avg_gain / avg_loss))`. The result is rounded to 2 decimal places.

### 5.3 MACD (Proxy)

A simplified MACD is computed as the difference between the 12-period and 26-period simple moving averages (as opposed to the standard exponential moving averages). The last 12 and last 26 prices are each summed and divided by their respective period lengths, and the 26-period SMA is subtracted from the 12-period SMA. The result is rounded to 4 decimal places.

### 5.4 Bollinger Bands (20-Day)

1. The 20-day SMA (`sma20`) is computed from the last 20 closing prices.
2. The sample standard deviation (`std20`) of the same 20 prices is computed using `statistics.stdev()`.
3. The upper band is `sma20 + 2 × std20` and the lower band is `sma20 - 2 × std20`. Both are rounded to 2 decimal places and returned as a nested dict with keys `upper` and `lower`.

### 5.5 Annualized Volatility

1. **Daily returns** are computed for each consecutive pair in the full price list: `(prices[i] / prices[i-1]) - 1`.
2. The sample standard deviation of all daily returns is computed via `statistics.stdev()`.
3. The result is scaled to an annualized figure by multiplying by √252 (the standard approximation for trading days per year). The final value is formatted as a percentage string (see [Section 4.7](#47-annualized-volatility-float--percentage-string)).

### 5.6 VADER Sentiment Scoring

Performed in `NewsSentimentTool._run_logic()`.

1. The VADER `SentimentIntensityAnalyzer.polarity_scores()` method is called for each extracted headline, producing a dict of sentiment scores. Only the `compound` key (a normalised score in the range `[-1.0, 1.0]`) is retained.
2. Scores of exactly `0` (headlines VADER found entirely neutral) are excluded from the aggregation via `[s for s in scores if s != 0]`.
3. The remaining scores are averaged by summing and dividing by their count. If all scores were zero, the average defaults to `0`.
4. The average is classified into a sentiment label: `"Positive"` if `> 0.15`, `"Negative"` if `< -0.15`, and `"Neutral"` otherwise. The average is also rounded to 3 decimal places and returned as `nlp_score`.

---

## 6. Threshold Evaluation & Risk Classification

Performed in `RiskFlagsTool._run_logic()`. The tool receives two pre-computed dicts (`tech` from `TechnicalIndicatorTool`, `fund` from `FundamentalsTool`) and evaluates four independent binary conditions against hard-coded thresholds. Each condition that is met appends a descriptive string to a `flags` list.

| Data Field | Source Dict | Condition | Flag Appended |
|---|---|---|---|
| `rsi` | `tech` | `> 70` | `"Overbought (RSI > 70)"` |
| `rsi` | `tech` | `< 30` | `"Oversold (RSI < 30)"` |
| `volatility` (after string→float conversion) | `tech` | `> 40` | `"High Volatility (> 40%)"` |
| `pe` | `fund` | `isinstance(pe, (int, float)) and pe > 50` | `"High Valuation (P/E: {pe})"` |

The P/E check additionally validates that the field is numeric before comparing, since the API may return `"N/A"` as a string. If `flags` is empty after all evaluations, it is replaced with the single-element list `["No high-risk flags identified."]` before being returned.

---

## 7. Data Aggregation

### 7.1 Consolidated Report Payload

`CalculateAllMetricsTool._run_logic()` functions as a facade that assembles a single unified dict by calling the `_run_logic` methods of five other tool classes directly (bypassing the `execute` wrapper and the registry dispatch). The individual return values are stored as nested values under descriptive keys:

```
{
    "ticker":                <str>   — passed through unchanged
    "price_metrics":         <dict>  — from CurrentPriceTool
    "technical_indicators":  <dict>  — from TechnicalIndicatorTool
    "fundamental_data":      <dict>  — from FundamentalsTool
    "sentiment_analysis":    <dict>  — from NewsSentimentTool
    "risk_flags":            <list>  — from RiskFlagsTool,
                                       consuming the tech and fund dicts above
}
```

The `risk_flags` value is produced last because `RiskFlagsTool` takes the already-computed `techs` and `funds` dicts as inputs, creating an internal data dependency within the aggregation step.

---

## 8. Conversation State Management

`StockAgent` maintains a mutable list (`self.history`) of `google.genai.types.Content` objects that represents the full multi-turn conversation sent to the model on every inference call.

### 8.1 User Prompt → `types.Content`

When `StockAgent.run(prompt)` is called, the raw user string is wrapped in a `types.Content` object with `role="user"` containing a single `types.Part` created via `types.Part.from_text(text=prompt)`. This object is appended to `self.history`.

### 8.2 Model Response → History

The model's response content object (`response.candidates[0].content`) is appended to `self.history` directly, without transformation. This preserves the model's role and part structure (whether a function call or a text response) in the conversation record.

### 8.3 Tool Result → `types.Content` (Function Response)

After a tool executes, its result (a `dict`, `list`, or `str`) is wrapped in a `types.Content` object with `role="user"` containing a `types.Part` created via `types.Part.from_function_response(name=fn.name, response={"result": result})`. The result is placed as the value under the key `"result"` within the response dict. This object is appended to `self.history`, completing the function-call turn.

### 8.4 History & Cache Clearing

`StockAgent.clear_history()` calls `self.history.clear()` to discard all accumulated `types.Content` objects, calls `self.registry.clear_all_caches()` to discard all cached API responses (see [Section 2](#2-in-memory-caching)), and resets `self.current_model_idx` to `0`. This resets the entire data state of the agent to its initial condition.

---

## 9. Tool Declaration Serialisation

### 9.1 Tool Declarations as Dicts

Each `BaseTool` subclass implements `get_declaration()`, which returns a plain Python `dict` conforming to the Google GenAI function declaration schema. This dict specifies the tool's `name`, `description`, and a `parameters` object that declares the expected argument names, types, and which are required.

These dicts are collected into a list comprehension — `[t.get_declaration() for t in self.registry.tools.values()]` — inside `StockAgent.run()` and passed to `types.Tool(function_declarations=[...])`, which the GenAI SDK serialises into the model request payload.

### 9.2 Function Call → Tool Dispatch

When the model decides to use a tool, the `function_call` field of the response part contains two data items: `fn.name` (a string matching a registered tool name) and `fn.args` (a dict of argument name-value pairs matching the declared parameter schema). These are passed directly to `ToolRegistry.run(fn.name, fn.args)`, which unpacks `fn.args` as keyword arguments into the tool's `execute()` method.

### 9.3 Error String Normalisation for Model Instructions

The system instruction sent with every model call instructs the model to halt immediately if any tool returns a value containing the words `"Error"` or `"Invalid"`. The same check is enforced in Python: the raw tool result is cast to `str` and inspected with `in` membership tests. This dual enforcement — in the system prompt and in Python — ensures the halt behaviour is consistent regardless of whether the model follows its instruction.

---

## 10. Input Sanitisation Pipeline

All operations are performed in `InputValidator` (`validator.py`) on the raw string read from stdin. Checks are applied in strict order; the first failure short-circuits the remaining checks.

### 10.1 Whitespace Normalisation

`user_input.strip()` is called at the start of `validate()`, removing leading and trailing whitespace before any check is applied. The same is done in `main.py` via `input(...).strip()`, meaning the string is stripped twice in practice.

### 10.2 Length Measurement

`len(user_input)` is measured against the hard-coded limit of `200`. This check operates on the stripped string and counts Unicode code points, not bytes.

### 10.3 Regex-Based Word Tokenisation

`re.findall(r'\b[a-zA-Z]+\b', user_input)` extracts all contiguous sequences of ASCII alphabetic characters, delimited by word boundaries. Digits, punctuation, and non-ASCII characters are all excluded from the token list.

### 10.4 Ticker-Aware Word Filtering

Tokens from step 10.3 are partitioned into "probable tickers" and "standard words". A token is treated as a probable ticker if `w.isupper()` returns `True` (i.e., it is entirely uppercase) or if its length is 1. Standard words are the remainder, lowercased for dictionary lookup.

If the token list is non-empty but the standard words list is empty (meaning the user typed only a ticker symbol), `_is_meaningful()` returns `True` immediately without performing a dictionary check.

### 10.5 Spell-Checker Dictionary Lookup

`self.spell.known(standard_words)` passes the lowercased standard words to `pyspellchecker`, which returns the subset that exists in its English dictionary. The validity ratio is computed as `len(known_words) / len(standard_words)`. The input is accepted as meaningful only if at least one word is known **and** the ratio is ≥ 0.40.

### 10.6 Character Allowlist Validation

`re.match(r'^[a-zA-Z0-9\s\.\,\?\'\"\-\:\$\%\&]+$', user_input)` checks that every character in the full input string (including digits and punctuation) belongs to the defined allowlist. Any character outside the set causes the check to fail.

### 10.7 Profanity Detection

`profanity.contains_profanity(user_input)` from the `better_profanity` library scans the input against its censor word list, which includes leet-speak and character-substitution obfuscations.

### 10.8 Prompt Injection Signature Matching

The input is lowercased (`user_input.lower()`) once and then checked with `in` membership tests against each string in `self.injection_signatures`. The lowercase conversion ensures case-insensitive matching without modifying the original input.

---

## 11. Output Formatting

### 11.1 Nested Dict → CLI Report String

`ReportFormattingTool._run_logic()` destructures the consolidated data dict from `CalculateAllMetricsTool` into five local variables (`p`, `t`, `f`, `s`, `r`) and uses a multi-line f-string to produce a fixed-width, section-labelled plain-text report.

The risk flags list (`r`) requires an extra conversion step: `chr(10).join(['- ' + flag for flag in r])` joins the list elements into a single string with literal newline characters, allowing the list to be embedded inline within the f-string without a loop.

The ticker string is forced to uppercase via `.upper()` before rendering to normalise inconsistent casing that may have been passed in.

### 11.2 Data → Truncated Console String

`ConsoleLogger._truncate()` converts any value to a string via `str(text)`, strips newline and carriage return characters using `.replace('\n', ' ').replace('\r', '')` (to keep output on a single line), and truncates to `max_length` characters, appending `"..."` if truncation occurred. This is applied to tool invocation logs (`"ACT"` events) and tool output logs (`"OBSERVE"` events), but deliberately not to final answers (`"FINAL"` events).

### 11.3 Model Error → Lowercased String (Quota Detection)

In `StockAgent.run()`, when a model API call raises an exception, `str(e).lower()` converts the exception message to a lowercase string. This normalised string is then checked for membership against the list `["429", "503", "quota", "exhausted", "overloaded"]` using a generator expression with `any()`, allowing case-insensitive detection of quota and demand errors across different exception message formats.
