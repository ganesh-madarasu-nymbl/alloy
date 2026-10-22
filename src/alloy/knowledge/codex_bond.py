"""Call Bond via Codex's saved OAuth session without an inference turn.

Uses the installed app-server JSON-RPC interface, not Codex's private credential store.
No model turn is started. Interactive requests are declined, never auto-approved.
"""

import asyncio
import json
from pathlib import Path

# app-server writes one JSON message per line; Bond results exceed asyncio's 64 KiB default.
STREAM_LIMIT = 16 * 1024 * 1024


class BondConnectionError(RuntimeError):
    pass


class CodexBond:
    def __init__(self, cwd: Path | None = None, timeout: float = 45):
        self.cwd = cwd or Path.cwd()
        self.timeout = timeout
        self.process = None
        self.sequence = 0

    async def __aenter__(self):
        try:
            self.process = await asyncio.create_subprocess_exec(
                "codex", "app-server", "--stdio",
                cwd=self.cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=STREAM_LIMIT,
            )
            await self.request("initialize", {
                "clientInfo": {"name": "alloy-bond", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            })
            await self.send({"method": "initialized"})
            return self
        except BaseException:
            await self.close()
            raise

    async def close(self):
        if self.process is not None:
            if self.process.returncode is None:
                try:
                    self.process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(self.process.wait(), 5)
                except TimeoutError:
                    self.process.kill()
                    await self.process.wait()
            self.process = None

    async def __aexit__(self, *_):
        await self.close()

    async def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        await self.process.stdin.drain()

    async def request(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        await self.send({"id": request_id, "method": method, "params": params})
        try:
            async with asyncio.timeout(self.timeout):
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        raise BondConnectionError(
                            "Codex MCP bridge could not start or exited. "
                            "Check Codex runtime access, then run alloy bond-check again."
                        )
                    message = json.loads(line)
                    if message.get("id") == request_id and "method" not in message:
                        if "error" in message:
                            raise BondConnectionError(f"Codex rejected {method}; check your installed CLI version.")
                        return message["result"]
                    if "id" in message and "method" in message:
                        await self.send({"id": message["id"], "error": {
                            "code": -32601, "message": "Interactive requests require the Codex client",
                        }})
                        raise BondConnectionError("Bond needs interactive authorization; run codex mcp login valency.")
        except TimeoutError as exc:
            raise BondConnectionError("Bond discovery timed out; check network access and Valency sign-in.") from exc

    async def inventory(self, thread_id=None):
        servers = []
        cursor = None
        while True:
            page = await self.request("mcpServerStatus/list", {
                "serverName": "valency", "detail": "toolsAndAuthOnly",
                "threadId": thread_id, "cursor": cursor,
            })
            servers.extend(page.get("data", []))
            cursor = page.get("nextCursor")
            if not cursor:
                break
        server = next((s for s in servers if s["name"] == "valency"), None)
        if server is None:
            raise BondConnectionError("Valency is absent from Codex; install and sign in to the Valency plugin.")
        if not server.get("tools"):
            raise BondConnectionError("Valency is configured but exposed no tools. Check network access and sign-in.")
        return server

    async def search(self, query: str, limit: int):
        # An ephemeral thread establishes MCP state; no turn/start or model request occurs.
        thread = await self.request("thread/start", {
            "cwd": str(self.cwd), "ephemeral": True, "approvalPolicy": "never", "sandbox": "read-only",
        })
        thread_id = thread["thread"]["id"]
        server = await self.inventory(thread_id)
        tools = server["tools"]
        # This is the read-only research tool named in Valency's installed workflows.
        if "semantic_search_papers" not in tools:
            raise BondConnectionError("Valency did not expose semantic_search_papers; inspect alloy bond-check.")
        result = await self.request("mcpServer/tool/call", {
            "threadId": thread_id, "server": "valency", "tool": "semantic_search_papers",
            "arguments": {"query": query, "limit": limit, "include_abstract": True, "max_authors": 3},
        })
        if result.get("isError"):
            raise BondConnectionError("Valency returned a search error; no papers were cached.")
        return result


def inspect_connection():
    async def run():
        async with CodexBond() as client:
            return await client.inventory()
    return asyncio.run(run())


def search_raw(query: str, limit: int):
    async def run():
        async with CodexBond() as client:
            return await client.search(query, limit)
    return asyncio.run(run())
