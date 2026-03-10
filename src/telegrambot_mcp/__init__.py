"""
telegrambot-mcp: A trusted, open-source Telegram MCP server.

Uses bot token authentication only — no personal account access required.
"""

from .server import mcp

__all__ = ["mcp"]
__version__ = "0.1.4"
