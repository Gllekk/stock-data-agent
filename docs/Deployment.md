# Deployment — Stock Data Agent

A step-by-step guide covering prerequisites, installation, configuration, startup, usage, and deployment strategy for the Stock Data Agent.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Dependencies](#3-dependencies)
4. [Environment Variable Configuration](#4-environment-variable-configuration)
5. [Starting the Application](#5-starting-the-application)
6. [Usage Guide](#6-usage-guide)
7. [Running the Test Suite](#7-running-the-test-suite)
8. [Deployment Strategy](#8-deployment-strategy)

---

## 1. Prerequisites

Before proceeding, ensure the following are available on the target machine:

| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.10+ | Required for `tuple[bool, str]` type hint syntax used in `validator.py` |
| pip | Any recent version | Used to install project dependencies |
| Git | Any version | Required to clone the repository |
| Google Gemini API Key | — | Must have access to at least one Gemini Flash model. See [Section 4](#4-environment-variable-configuration) |

Internet access is required at runtime — the agent makes live requests to Yahoo Finance and Google News RSS.

---

## 2. Installation

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

## 3. Dependencies

The following third-party packages are required by the project. All are available on PyPI.

### Runtime Dependencies

These packages are required to run the application.

| Package | Import Name | Used In | Purpose |
|---|---|---|---|
| `google-genai` | `google.genai` | `agent.py` | Official Google Generative AI Python SDK — used to initialise the client, send prompts with tool declarations, and parse model responses |
| `vaderSentiment` | `vaderSentiment.vaderSentiment` | `tools.py` | Rule-based NLP sentiment analyser — used by `NewsSentimentTool` to score news headlines and classify overall sentiment as Positive, Neutral, or Negative |
| `pyspellchecker` | `spellchecker` | `validator.py` | English dictionary lookup library — used by `InputValidator._is_meaningful()` to calculate the ratio of recognisable words in the user's input |
| `better-profanity` | `better_profanity` | `validator.py` | Profanity detection library with obfuscation awareness — used by `InputValidator.validate()` to screen for inappropriate language |

### Standard Library

The following modules are used extensively but are part of Python's standard library and require no installation:

`os`, `sys`, `json`, `re`, `datetime`, `statistics`, `typing`, `urllib.request`, `urllib.parse`, `abc`

### Development Dependencies

This package is required to run the test suite and is not needed in production.

| Package | Purpose |
|---|---|
| `pytest` | Test discovery and execution framework |

---

## 4. Environment Variable Configuration

The application requires exactly one environment variable to be set before startup.

### `GEMINI_API_KEY`

| Property | Value |
|---|---|
| **Required** | Yes — the application exits immediately at startup if this variable is not set |
| **Description** | A valid API key for the Google Gemini API, used to authenticate all model inference requests |
| **Where to obtain** | [Google AI Studio](https://aistudio.google.com/app/apikey) |

**Setting the variable for a single session:**

On macOS / Linux:
```
export GEMINI_API_KEY="your_api_key_here"
```

On Windows (Command Prompt):
```
set GEMINI_API_KEY=your_api_key_here
```

On Windows (PowerShell):
```
$env:GEMINI_API_KEY="your_api_key_here"
```

**Setting the variable persistently:**

To avoid re-exporting the key on every new terminal session, add the `export` line to your shell's profile file (e.g., `~/.bashrc`, `~/.zshrc`, or `~/.profile`) and reload it:

```
echo 'export GEMINI_API_KEY="your_api_key_here"' >> ~/.zshrc
source ~/.zshrc
```

**Using a `.env` file (optional):**

If you prefer to manage environment variables via a `.env` file, tools such as [`python-dotenv`](https://pypi.org/project/python-dotenv/) or the `direnv` shell extension can load the file automatically. The `.env` file should be added to `.gitignore` and must never be committed to version control, as it contains a secret key.

### Model Access

The agent's fallback model list (configured in `StockAgent.__init__`) currently includes the following models, attempted in order when quota or availability issues arise:

```
gemini-3.1-flash-lite-preview
gemini-3-flash-preview
gemini-2.5-flash
gemini-2.5-flash-lite
```

Ensure the API key being used has access to at least the first model in this list. If access to certain preview models is unavailable, update the `available_models` list in `agent.py` accordingly before running the application.

---

## 5. Starting the Application

The application is a command-line interface and is started by running `main.py` from the **project root directory**. The project root must be the working directory because `main.py` uses a relative path (`..`) to locate the `stock_agent` package under `src/`.

```
python src/stock_agent/main.py
```

On a successful start, the following banner is printed to the terminal:

```
--- Stock Analysis System Initialized ---
Commands: 'exit' or 'quit' to quit
          'clear' to reset history

[USER] Ask about a stock:
```

If the `GEMINI_API_KEY` variable is missing or the agent fails to initialise, an error message is printed and the process exits with code `1`.

---

## 6. Usage Guide

Once started, the application runs an interactive read–validate–execute loop. The user types a query at the `[USER]` prompt, and the agent processes it and prints a response.

### System Commands

The following reserved inputs control the application itself and are not forwarded to the agent:

| Command | Action |
|---|---|
| `exit` or `quit` | Gracefully shuts down the application |
| `clear` | Clears the agent's conversation history and all data caches, and resets the active model to the primary one. Useful for starting a fresh analysis without restarting the process |
| `Ctrl+C` | Interrupts the process and shuts down gracefully at any point |

### Accepted Query Types

The following query types are supported. All queries must be in standard English, under 200 characters, and free of special characters outside the set `` a–z A–Z 0–9 spaces . , ? ' " - : $ % & ``.

| Query Type | Example |
|---|---|
| Current price | `What is the current price of TSLA?` |
| Price on a specific date | `What was Apple's price on 2024-06-10?` |
| Technical indicators | `Give me the RSI and Bollinger Bands for MSFT.` |
| Fundamental data | `What are the fundamentals for Amazon?` |
| News sentiment | `What is the sentiment around Rheinmetall?` |
| Risk flags | `What are some risk flags for Nvidia?` |
| Full analysis report | `Give me a full report on Coca-Cola.` |
| Ticker symbol alone | `AAPL` |

### Input Validation

All input is screened by `InputValidator` before reaching the agent. Queries that fail any of the following checks are rejected with an explanatory message and the user is prompted again — no API quota is consumed:

| Check | Condition That Causes Rejection |
|---|---|
| Empty | Blank or whitespace-only input |
| Length | More than 200 characters |
| Gibberish | Fewer than 40% of non-ticker words recognised by the English dictionary |
| Invalid characters | Any character outside the allowed set |
| Profanity | Inappropriate or obfuscated language |
| Prompt injection | Presence of known injection signatures (e.g., `"ignore all previous"`) |

### Console Output Format

During execution, the agent prints colour-coded status lines to the terminal:

| Colour | Prefix | Meaning |
|---|---|---|
| Cyan | `[USER]` | The user's input prompt |
| Magenta | `[AGENT]` | A tool invocation or the final answer |
| Yellow | `[SYSTEM]` | The raw output returned by a tool |
| Red | `[ERROR]` | A validation failure, API error, or unexpected exception |

---

## 7. Running the Test Suite

The test suite requires no environment variables and makes no real network or API calls. Run it from the **project root directory**:

```
pytest
```

To run with verbose output showing individual test names:

```
pytest -v
```

To run a single test module:

```
pytest tests/test_tools.py
```

All 29 tests should pass. For a full breakdown of the test suite's structure and coverage, refer to `Testing.md`.

---

## 8. Deployment Strategy

The Stock Data Agent is a stateless, interactive CLI application with no persistent storage, no web server, and no database. Its deployment requirements are therefore minimal. The appropriate strategy depends on the intended use case.

### Local Developer Machine (Primary Use Case)

This is the most straightforward deployment. Follow Sections 1–5 of this document. 

### Containerised Deployment (Docker)

For a reproducible, portable environment, the application can be containerised. A minimal `Dockerfile` placed at the project root would follow this structure:

```
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
CMD ["python", "src/stock_agent/main.py"]
```

Build and run with:

```
docker build -t stock-data-agent .
docker run -it -e GEMINI_API_KEY="your_api_key_here" stock-data-agent
```

The `-it` flag is required because the application reads from stdin interactively. The API key is passed securely via the `-e` flag rather than being baked into the image. Note that the key must never appear in the `Dockerfile` or in any file committed to version control.

### Security Considerations

- **API key handling:** The `GEMINI_API_KEY` must be treated as a secret. Use environment variables or a secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault) rather than hardcoding or committing it.
- **No inbound network exposure:** The application does not bind to any port or expose a network interface, so no firewall rules or TLS configuration are needed.
- **Input validation:** All user input is validated locally by `InputValidator` before reaching the model, guarding against prompt injection and malformed queries.
