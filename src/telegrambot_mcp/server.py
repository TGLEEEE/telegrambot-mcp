#!/usr/bin/env python3
"""
telegrambot-mcp — Telegram MCP Server
======================================
A trusted, open-source MCP server for Telegram using **bot token authentication only**.
No personal account access. No proprietary backend.

Required environment variables:
  TELEGRAM_BOT_TOKEN  — Bot token from @BotFather
  TELEGRAM_CHAT_ID    — Target chat ID (user, group, or channel)

Tools:
  send_message                   — Free-form text message
  send_notification              — Structured notification with event emoji
  send_notification_with_buttons — Notification with up to 4 inline buttons
  send_photo                     — Send an image (URL or local file path)
  send_document                  — Send any file (URL or local file path)
  wait_for_reply                 — Block until user replies (smart polling)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Literal

import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "telegrambot-mcp",
    instructions=(
        "Telegram bot MCP server (telegrambot-mcp). "
        "Use these tools to send messages, notifications, photos, and files "
        "via Telegram and to wait for replies from the user.\n\n"
        "wait_for_reply captures BOTH button taps AND free-form typed messages — "
        "no prefix required. Users can always ignore buttons and just type freely.\n\n"
        "IMPORTANT: Always respond to the user in their own language — "
        "never hardcode a specific language in your messages."
    ),
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

TELEGRAM_API = "https://api.telegram.org"

# Tracks the latest processed update_id to skip stale messages.
_last_update_id: int = 0


def _token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Export it before starting the MCP server."
        )
    return token


def _chat_id() -> str:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID is not set. "
            "Export it before starting the MCP server."
        )
    return chat_id


def _post(method: str, payload: dict) -> dict | list:
    """Send a JSON request to the Telegram Bot API and return the result."""
    url = f"{TELEGRAM_API}/bot{_token()}/{method}"
    with httpx.Client(timeout=35) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram API error [{method}]: {data.get('description', 'unknown error')}"
        )
    return data["result"]


def _post_file(method: str, field: str, source: str, extra: dict) -> dict:
    """Upload a file (local path or URL) to the Telegram Bot API."""
    url = f"{TELEGRAM_API}/bot{_token()}/{method}"
    extra["chat_id"] = _chat_id()

    if source.startswith("http://") or source.startswith("https://"):
        # URL — Telegram fetches it directly; no upload needed.
        extra[field] = source
        with httpx.Client(timeout=60) as client:
            response = client.post(url, json=extra)
    else:
        # Local file — upload as multipart form data.
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {source}")
        with path.open("rb") as f, httpx.Client(timeout=120) as client:
            response = client.post(url, data=extra, files={field: (path.name, f)})

    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram API error [{method}]: {data.get('description', 'unknown error')}"
        )
    return data["result"]


# ---------------------------------------------------------------------------
# Event emoji mapping
# ---------------------------------------------------------------------------

_EVENT_EMOJI: dict[str, str] = {
    "completed": "✅",
    "error": "❌",
    "progress": "🔄",
    "question": "❓",
}

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Send a free-form text message to the configured Telegram chat.\n\n"
        "Use this for casual messages, inline code snippets, status updates, "
        "or any content that does not require structured formatting.\n\n"
        "Args:\n"
        "  text       : The message body. Supports Telegram Markdown v1 by default.\n"
        "  parse_mode : 'Markdown', 'HTML', or '' for plain text. Default: 'Markdown'."
    )
)
def send_message(
    text: str,
    parse_mode: Literal["Markdown", "HTML", ""] = "Markdown",
) -> str:
    """Send a free-form text message."""
    payload: dict = {"chat_id": _chat_id(), "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    result = _post("sendMessage", payload)
    assert isinstance(result, dict)
    return f"Message sent (message_id={result['message_id']})"


@mcp.tool(
    description=(
        "Send a structured notification to the configured Telegram chat.\n\n"
        "Automatically prepends an emoji for quick visual scanning. "
        "Default emojis by event type:\n"
        "  completed → ✅   error → ❌   progress → 🔄   question → ❓\n\n"
        "Override the default emoji with the icon parameter when the context calls "
        "for something more specific (e.g. icon='🚀' for a deployment, "
        "'🧪' for a test run, '📊' for a report).\n\n"
        "Args:\n"
        "  event   : Event type — 'completed', 'error', 'progress', or 'question'.\n"
        "  summary : One-line summary shown prominently (≤200 chars recommended).\n"
        "  details : Optional multi-line body — stack traces, next steps, metrics, etc.\n"
        "  icon    : Optional emoji to override the default event icon."
    )
)
def send_notification(
    event: Literal["completed", "error", "progress", "question"],
    summary: str,
    details: str = "",
    icon: str = "",
) -> str:
    """Send a structured event notification."""
    emoji = icon.strip() or _EVENT_EMOJI.get(event, "ℹ️")
    parts = [f"{emoji} *{summary}*"]
    if details:
        parts.append(f"\n{details}")
    text = "\n".join(parts)

    result = _post("sendMessage", {"chat_id": _chat_id(), "text": text, "parse_mode": "Markdown"})
    assert isinstance(result, dict)
    return f"Notification sent (event={event}, message_id={result['message_id']})"


@mcp.tool(
    description=(
        "Send a structured notification with up to 4 inline action buttons.\n\n"
        "Buttons let the user reply with a single tap instead of typing. "
        "After sending, call wait_for_reply to capture the chosen button or typed reply.\n\n"
        "Button design guidelines:\n"
        "  - Provide 2–4 buttons with clear, action-oriented labels.\n"
        "  - Keep each label under 30 characters.\n"
        "  - Buttons are suggestions — users can always type a custom reply instead.\n"
        "  - Use emoji prefixes in labels to aid scannability (e.g. '✅ Approve', '❌ Cancel').\n\n"
        "Args:\n"
        "  event   : Event type — 'completed', 'error', 'progress', or 'question'.\n"
        "  summary : One-line summary (≤200 chars).\n"
        "  buttons : List of 1–4 button label strings. "
                    "Each label becomes the button text AND the callback payload.\n"
        "  details : Optional additional context or instructions for the user.\n"
        "  icon    : Optional emoji to override the default event icon."
    )
)
def send_notification_with_buttons(
    event: Literal["completed", "error", "progress", "question"],
    summary: str,
    buttons: list[str],
    details: str = "",
    icon: str = "",
) -> str:
    """Send a notification with up to 4 inline keyboard buttons."""
    if not buttons:
        raise ValueError("Provide at least one button label.")
    if len(buttons) > 4:
        raise ValueError("A maximum of 4 buttons is allowed.")

    emoji = icon.strip() or _EVENT_EMOJI.get(event, "ℹ️")
    parts = [f"{emoji} *{summary}*"]
    if details:
        parts.append(f"\n{details}")
    text = "\n".join(parts)

    # One button per row keeps the layout clean on mobile
    keyboard = [
        [{"text": label, "callback_data": label[:64]}]
        for label in buttons
    ]

    payload = {
        "chat_id": _chat_id(),
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": keyboard},
    }
    result = _post("sendMessage", payload)
    assert isinstance(result, dict)
    return (
        f"Notification with {len(buttons)} button(s) sent "
        f"(message_id={result['message_id']})"
    )


@mcp.tool(
    description=(
        "Send an image to the configured Telegram chat.\n\n"
        "The image is displayed inline in the chat (not as a file attachment). "
        "Supports JPEG, PNG, GIF, WebP up to 10 MB.\n\n"
        "Args:\n"
        "  photo   : URL (https://...) or absolute local file path to the image.\n"
        "  caption : Optional caption shown below the image. Markdown supported."
    )
)
def send_photo(
    photo: str,
    caption: str = "",
) -> str:
    """Send an image by URL or local file path."""
    extra: dict = {}
    if caption:
        extra["caption"] = caption
        extra["parse_mode"] = "Markdown"

    result = _post_file("sendPhoto", "photo", photo, extra)
    return f"Photo sent (message_id={result['message_id']})"


@mcp.tool(
    description=(
        "Send any file as a document attachment to the configured Telegram chat.\n\n"
        "Use this for PDFs, CSVs, logs, ZIPs, code files, or any binary/text file. "
        "The file appears as a downloadable attachment (not inline). "
        "Max file size: 50 MB.\n\n"
        "Args:\n"
        "  document : URL (https://...) or absolute local file path to the file.\n"
        "  caption  : Optional caption shown with the attachment. Markdown supported."
    )
)
def send_document(
    document: str,
    caption: str = "",
) -> str:
    """Send a file by URL or local file path."""
    extra: dict = {}
    if caption:
        extra["caption"] = caption
        extra["parse_mode"] = "Markdown"

    result = _post_file("sendDocument", "document", document, extra)
    return f"Document sent (message_id={result['message_id']})"


@mcp.tool(
    description=(
        "Wait for a reply from the user via Telegram and return it.\n\n"
        "Handles both plain text messages and inline button taps (callback queries).\n\n"
        "Smart polling intervals (minimises API calls):\n"
        "  0 – 10 min elapsed  →  poll every 30 s\n"
        "  10 min – 1 hr       →  poll every 60 s\n"
        "  1 hr+               →  poll every 120 s\n\n"
        "LLM guidelines for choosing max_wait_seconds:\n"
        "  Simple yes/no or quick question  →  300    (5 min)\n"
        "  General task approval            →  1 800  (30 min)  ← default\n"
        "  Stock price / alert trigger      →  1 800  (30 min)\n"
        "  End-of-day review                →  7 200  (2 hr)\n"
        "  Overnight / long-running job     →  21 600 (6 hr)  ← maximum\n\n"
        "Args:\n"
        "  max_wait_seconds : How long to wait. Default 1800, maximum 21600. "
                              "Pick a value appropriate to how soon a reply is expected."
    )
)
def wait_for_reply(max_wait_seconds: int = 1800) -> str:
    """Block until the user replies or the timeout expires."""
    global _last_update_id

    max_wait_seconds = max(1, min(max_wait_seconds, 21_600))
    start = time.monotonic()

    # Prime the offset: ignore messages that arrived before this call.
    if _last_update_id == 0:
        try:
            updates = _post("getUpdates", {"limit": 1, "timeout": 0})
            assert isinstance(updates, list)
            if updates:
                _last_update_id = updates[-1]["update_id"]
        except Exception:
            pass  # Non-fatal; we'll just process any queued messages.

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= max_wait_seconds:
            return (
                f"Timed out after {int(elapsed)} seconds — no reply received."
            )

        # Determine how long to hold the long-poll connection open.
        if elapsed < 600:
            poll_interval = 30
        elif elapsed < 3600:
            poll_interval = 60
        else:
            poll_interval = 120

        remaining = max_wait_seconds - elapsed
        long_poll_timeout = min(poll_interval, int(remaining))

        try:
            updates = _post(
                "getUpdates",
                {
                    "offset": _last_update_id + 1,
                    "timeout": long_poll_timeout,
                    "allowed_updates": ["message", "callback_query"],
                },
            )
        except Exception:
            # Transient network error — back off briefly and retry.
            time.sleep(5)
            continue

        assert isinstance(updates, list)
        for update in updates:
            uid: int = update["update_id"]
            _last_update_id = max(_last_update_id, uid)

            if "message" in update:
                msg = update["message"]
                user = msg.get("from", {})
                name = user.get("first_name", "User")
                text = msg.get("text", "(non-text message)")
                return f"Reply from {name}: {text}"

            if "callback_query" in update:
                cq = update["callback_query"]
                user = cq.get("from", {})
                name = user.get("first_name", "User")
                data = cq.get("data", "")
                # Acknowledge the tap to clear the loading spinner on the button.
                try:
                    _post("answerCallbackQuery", {"callback_query_id": cq["id"]})
                except Exception:
                    pass
                return f"Button tapped by {name}: {data}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the MCP server using stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
