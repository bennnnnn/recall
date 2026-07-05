from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# asyncpg rejects libpq-style query params passed as connect() kwargs
_STRIP_QUERY_KEYS = frozenset({"sslmode", "channel_binding"})


def prefer_neon_pooler_hostname(host: str) -> str:
    """Rewrite a direct Neon host to the pooler endpoint when applicable."""
    if not host or "-pooler" in host or ".pooler." in host or "neon.tech" not in host:
        return host
    labels = host.split(".")
    if not labels:
        return host
    labels[0] = f"{labels[0]}-pooler"
    return ".".join(labels)


def prepare_asyncpg_url(url: str, *, prefer_neon_pooler: bool = False) -> tuple[str, dict]:
    """Return (clean_url, connect_args) for SQLAlchemy + asyncpg."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if prefer_neon_pooler:
        pooled = prefer_neon_pooler_hostname(hostname)
        if pooled != hostname:
            netloc = parsed.netloc.replace(hostname, pooled, 1)
            parsed = parsed._replace(netloc=netloc)
            hostname = pooled

    query = parse_qs(parsed.query)
    ssl_required = query.get("sslmode", [None])[0] == "require" or "neon.tech" in hostname
    kept: list[tuple[str, str]] = []
    for key, values in query.items():
        if key in _STRIP_QUERY_KEYS:
            continue
        for value in values:
            kept.append((key, value))
    clean = urlunparse(parsed._replace(query=urlencode(kept)))
    connect_args = {"ssl": "require"} if ssl_required else {}
    return clean, connect_args


def pool_recycle_seconds_for_url(url: str) -> int:
    """Longer recycle on Neon pooler — direct endpoints benefit from shorter churn."""
    if "-pooler" in url or ".pooler." in url:
        return 1800
    return 300
