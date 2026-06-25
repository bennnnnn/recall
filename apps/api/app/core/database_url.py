from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# asyncpg rejects libpq-style query params passed as connect() kwargs
_STRIP_QUERY_KEYS = frozenset({"sslmode", "channel_binding"})


def prepare_asyncpg_url(url: str) -> tuple[str, dict]:
    """Return (clean_url, connect_args) for SQLAlchemy + asyncpg."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    ssl_required = (
        query.get("sslmode", [None])[0] == "require" or "neon.tech" in (parsed.hostname or "")
    )
    kept: list[tuple[str, str]] = []
    for key, values in query.items():
        if key in _STRIP_QUERY_KEYS:
            continue
        for value in values:
            kept.append((key, value))
    clean = urlunparse(parsed._replace(query=urlencode(kept)))
    connect_args = {"ssl": "require"} if ssl_required else {}
    return clean, connect_args
