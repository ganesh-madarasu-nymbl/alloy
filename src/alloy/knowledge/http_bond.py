"""Call Bond over Valency's MCP HTTP endpoint with a bearer token; no Codex or Claude.

The token comes from Valency's OAuth sign-in. When it expires, the refresh token renews
it, and the renewed pair is kept in the cache dir so a hosted app survives restarts.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from alloy.config import settings
from alloy.knowledge.codex_bond import BondConnectionError

TOKEN_URL = "https://oauth.valency.io/token"
PROTOCOL = "2025-06-18"


def _token_cache():
    return settings.cache_dir / ".valency_tokens.json"


class HttpBond:
    def __init__(self, url: str | None = None, timeout: float = 60):
        self.url = url or settings.valency_mcp_url
        if not self.url:
            raise BondConnectionError("VALENCY_MCP_URL is not set; see .env.example")
        self.timeout = timeout
        self.session = None
        self.sequence = 0
        cached = self._cached()
        self.token = cached.get("access_token") or settings.valency_token
        self.refresh_tokens = [
            t
            for t in (cached.get("refresh_token"), os.getenv("VALENCY_REFRESH_TOKEN"))
            if t
        ]

    @staticmethod
    def _cached() -> dict:
        try:
            return json.loads(_token_cache().read_text())
        except (OSError, ValueError):
            return {}

    def refresh(self) -> bool:
        client_id = os.getenv("VALENCY_CLIENT_ID")
        for refresh_token in self.refresh_tokens if client_id else []:
            body = urllib.parse.urlencode(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "resource": self.url.rstrip("/"),
                }
            ).encode()
            req = urllib.request.Request(
                TOKEN_URL, data=body, headers={"User-Agent": "alloy"}
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    tokens = json.load(r)
            except (urllib.error.URLError, ValueError):
                continue
            self.token = tokens["access_token"]
            # Refresh tokens may rotate, so the newest pair must outlive this process.
            saved = {
                "access_token": self.token,
                "refresh_token": tokens.get("refresh_token", refresh_token),
            }
            _token_cache().write_text(json.dumps(saved))
            _token_cache().chmod(0o600)
            self.refresh_tokens = [saved["refresh_token"]]
            return True
        return False

    def post(self, message: dict, retry: bool = True):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "alloy",
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(
            self.url, data=json.dumps(message).encode(), headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                self.session = r.headers.get("Mcp-Session-Id") or self.session
                ctype = r.headers.get("Content-Type", "")
                body = r.read().decode()
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and retry and self.refresh():
                return self.post(message, retry=False)
            if exc.code == 401:
                raise BondConnectionError(
                    "Bond sign-in is missing or expired; set VALENCY_TOKEN or sign in again."
                ) from exc
            raise BondConnectionError(f"Bond returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise BondConnectionError(
                "Could not reach Bond; check network access."
            ) from exc
        if "id" not in message or not body.strip():
            return None
        if "text/event-stream" in ctype:
            replies = [
                json.loads(line[5:])
                for line in body.splitlines()
                if line.startswith("data:") and line[5:].strip()
            ]
        else:
            replies = [json.loads(body)]
        reply = next((m for m in replies if m.get("id") == message["id"]), None)
        if reply is None:
            raise BondConnectionError(f"Bond sent no reply to {message['method']}")
        if "error" in reply:
            raise BondConnectionError(
                f"Bond rejected {message['method']}: {reply['error']}"
            )
        return reply["result"]

    def request(self, method: str, params: dict | None = None):
        self.sequence += 1
        return self.post(
            {
                "jsonrpc": "2.0",
                "id": self.sequence,
                "method": method,
                "params": params or {},
            }
        )

    def open(self):
        self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "alloy", "version": "0.1.0"},
            },
        )
        self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def tools(self) -> list[str]:
        names, cursor = [], None
        while True:
            page = self.request("tools/list", {"cursor": cursor} if cursor else {})
            names += [t["name"] for t in page.get("tools", [])]
            cursor = page.get("nextCursor")
            if not cursor:
                return names

    def call(self, tool: str, arguments: dict) -> dict:
        return self.request("tools/call", {"name": tool, "arguments": arguments})


def inspect_connection() -> dict:
    tools = HttpBond().open().tools()
    if not tools:
        raise BondConnectionError("Bond exposed no tools; check the token.")
    return {
        "name": "valency",
        "authStatus": "bearer",
        "runtimeStatus": "ok",
        "tools": tools,
    }


def search_raw(query: str, limit: int) -> dict:
    result = (
        HttpBond()
        .open()
        .call(
            "semantic_search_papers",
            {
                "query": query,
                "limit": limit,
                "include_abstract": True,
                "max_authors": 3,
            },
        )
    )
    if result.get("isError"):
        raise BondConnectionError(
            "Valency returned a search error; no papers were cached."
        )
    return result
