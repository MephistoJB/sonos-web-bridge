"""Psono MCP client for Sonos Web Bridge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant


class PsonoClient:
    """Small JSON-RPC client for the configured Psono MCP server."""

    def __init__(self, session: ClientSession, url: str, bearer_token: str) -> None:
        self._session = session
        self._url = url
        self._bearer_token = bearer_token
        self._session_id: str | None = None
        self._next_id = 1

    @classmethod
    async def async_from_config(
        cls,
        hass: HomeAssistant,
        session: ClientSession,
        url: str,
        bearer_token: str,
        bearer_token_file: str,
    ) -> "PsonoClient | None":
        """Create a client when enough authentication data is configured."""
        token = bearer_token.strip()
        if not token and bearer_token_file:
            token = (
                await hass.async_add_executor_job(_read_token_file, bearer_token_file)
            ).strip()
        if not url or not token:
            return None
        return cls(session, url, token)

    async def get_secret(self, name: str) -> str:
        """Read one secret value."""
        if not self._session_id:
            await self._initialize()
        result = await self._rpc("tools/call", {"name": "get_secret", "arguments": {"name": name}})
        content = result.get("content") or []
        if content and isinstance(content[0], dict) and isinstance(content[0].get("text"), str):
            payload = json.loads(content[0]["text"])
        else:
            payload = result.get("structuredContent") or {}
        value = payload.get("value")
        if not isinstance(value, str):
            raise RuntimeError(f"Psono key {name} did not return a string value")
        return value

    async def _initialize(self) -> None:
        await self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "sonos-web-bridge", "version": "0.1.0"},
            },
            allow_without_session=True,
        )

    async def _rpc(self, method: str, params: dict[str, Any], allow_without_session: bool = False) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        headers = {
            "Authorization": f"Bearer {self._bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id and not allow_without_session:
            headers["Mcp-Session-Id"] = self._session_id
        async with self._session.post(
            self._url,
            headers=headers,
            json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        ) as response:
            text = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"Psono MCP returned HTTP {response.status}")
            self._session_id = response.headers.get("Mcp-Session-Id", self._session_id)
        message = _parse_sse_json(text)
        if "error" in message:
            raise RuntimeError(str(message["error"].get("message") or message["error"]))
        result = message.get("result")
        if not isinstance(result, dict):
            return {}
        return result


def _parse_sse_json(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(text)


def _read_token_file(path: str) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8")
