# tgbot-mcp

[![PyPI version](https://img.shields.io/pypi/v/tgbot-mcp)](https://pypi.org/project/tgbot-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/tgbot-mcp)](https://pypi.org/project/tgbot-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **trusted, open-source** [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server for Telegram.

Built as a clean alternative to closed-source or opaque Telegram MCP packages — **bot token authentication only**, no personal account access, no proprietary backend.

---

## Features

- **Bot token auth only** — uses the official Telegram Bot API (`api.telegram.org`). Your personal account is never touched.
- **4 purpose-built tools** for LLM workflows: send messages, send structured notifications, send notifications with action buttons, and wait for user replies.
- **Language-agnostic** — tools are written in English, but the LLM responds to users in their own language automatically. No language is hardcoded.
- **Smart polling** in `wait_for_reply` to minimise API calls while staying responsive.
- Zero external services. Pure Python + [httpx](https://www.python-httpx.org/) + [fastmcp](https://github.com/jlowin/fastmcp).

---

## Quick Start

### 1. Create a Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts.
3. Copy the **bot token** (looks like `123456:ABC-DEF...`).
4. Start a chat with your new bot, then visit:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   Send any message to the bot and look for `"chat":{"id":...}` — that is your **chat ID**.

### 2. Install

```bash
pip install tgbot-mcp
```

### 3. Set Environment Variables

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="987654321"
```

### 4. Register with Your MCP Client

Add the following to your MCP client configuration (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "tgbot-mcp": {
      "command": "tgbot-mcp",
      "env": {
        "TELEGRAM_BOT_TOKEN": "YOUR_BOT_TOKEN",
        "TELEGRAM_CHAT_ID": "YOUR_CHAT_ID"
      }
    }
  }
}
```

Or run directly:

```bash
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... tgbot-mcp
```

---

## Tools

### `send_message`

Send a free-form text message to the configured chat.

| Parameter    | Type                        | Default      | Description                                |
|--------------|-----------------------------|--------------|--------------------------------------------|
| `text`       | `str`                       | *(required)* | Message body. Telegram Markdown supported. |
| `parse_mode` | `"Markdown" \| "HTML" \| ""` | `"Markdown"` | Text formatting mode.                      |

**Example prompt:** *"Send a Telegram message: 'Build finished successfully in 2m 14s.'"*

---

### `send_notification`

Send a structured notification with an automatic event emoji.

| Event       | Emoji |
|-------------|-------|
| `completed` | ✅    |
| `error`     | ❌    |
| `progress`  | 🔄    |
| `question`  | ❓    |

| Parameter | Type   | Default      | Description                          |
|-----------|--------|--------------|--------------------------------------|
| `event`   | `str`  | *(required)* | One of the four event types above.   |
| `summary` | `str`  | *(required)* | One-line summary (≤200 chars).       |
| `details` | `str`  | `""`         | Optional multi-line detail body.     |

**Example prompt:** *"Notify me on Telegram that the data pipeline completed. Include row counts."*

---

### `send_notification_with_buttons`

Send a notification with up to **4 inline action buttons**. Ideal when you want the user to pick an option without typing.

| Parameter | Type        | Default      | Description                                             |
|-----------|-------------|--------------|--------------------------------------------------------|
| `event`   | `str`       | *(required)* | Event type.                                             |
| `summary` | `str`       | *(required)* | One-line summary.                                       |
| `buttons` | `list[str]` | *(required)* | 1–4 button labels. Each label is also the reply value. |
| `details` | `str`       | `""`         | Optional context text.                                  |

**Example prompt:** *"Ask me via Telegram whether to deploy to staging or production."*

---

### `wait_for_reply`

Block until the user replies (text message or button tap) or the timeout expires.

| Parameter           | Type  | Default | Max    | Description                         |
|---------------------|-------|---------|--------|-------------------------------------|
| `max_wait_seconds`  | `int` | `1800`  | `21600`| How long to wait for a reply.       |

**Smart polling schedule:**

| Elapsed time      | Poll interval |
|-------------------|---------------|
| 0 – 10 minutes    | 30 seconds    |
| 10 minutes – 1 hr | 60 seconds    |
| 1 hr+             | 120 seconds   |

**LLM guidelines for `max_wait_seconds`:**

| Scenario                        | Recommended value |
|---------------------------------|-------------------|
| Simple yes/no question          | `300` (5 min)     |
| General task approval           | `1800` (30 min) ✓ |
| Stock price / event alert       | `1800` (30 min)   |
| End-of-day review               | `7200` (2 hr)     |
| Overnight / long-running job    | `21600` (6 hr)    |

---

## Typical LLM Workflow

```
LLM: [does some long task]
  → send_notification_with_buttons(
        event="question",
        summary="Finished analysis. What should I do next?",
        buttons=["📊 Generate report", "📧 Send email", "🔁 Re-run with new params"]
    )
  → wait_for_reply(max_wait_seconds=1800)
  → [user taps "📊 Generate report"]
LLM: [generates the report]
  → send_notification(event="completed", summary="Report ready!", details="...")
```

---

## Environment Variables

| Variable              | Required | Description                    |
|-----------------------|----------|--------------------------------|
| `TELEGRAM_BOT_TOKEN`  | ✅        | Bot token from @BotFather      |
| `TELEGRAM_CHAT_ID`    | ✅        | Chat ID to send messages to    |

---

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/TGLEEEE/tgbot-mcp
cd tgbot-mcp
pip install -e ".[dev]"

# Run directly
TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python -m tgbot_mcp.server
```

---

## Security

- Only the official Telegram Bot API is used (`api.telegram.org`). No third-party relay.
- Bot tokens are read from environment variables — never hardcoded.
- Only the chat configured via `TELEGRAM_CHAT_ID` receives messages.
- No personal Telegram account credentials are ever required.

---

## License

MIT — see [LICENSE](LICENSE).
