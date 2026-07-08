"""Pooled, keep-alive httpx.AsyncClient shared across outbound gateway calls.

Each external gateway (Tavily, Google Calendar, Gmail) used to open a fresh
httpx.AsyncClient per call, paying a new TCP+TLS handshake every time even
for repeated calls to the same host within seconds. Gateways call
get_pooled_client(timeout) instead, which lazily creates one client per
distinct timeout value and reuses it (keep-alive connection pooling) for the
life of the process.
"""

from __future__ import annotations

import httpx

_clients: dict[float, httpx.AsyncClient] = {}


def get_pooled_client(timeout: float) -> httpx.AsyncClient:
    client = _clients.get(timeout)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(timeout=timeout)
        _clients[timeout] = client
    return client


async def aclose_pooled_clients() -> None:
    """Release pooled connections on app shutdown."""
    clients = list(_clients.values())
    _clients.clear()
    for client in clients:
        await client.aclose()
