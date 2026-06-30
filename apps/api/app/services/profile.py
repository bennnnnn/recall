"""Profile display helpers — shared name normalization for API updates."""


def normalize_display_name(raw: str | None) -> str | None:
    """Trim, collapse whitespace, and enforce length for user-visible names."""
    if raw is None:
        return None
    name = " ".join(raw.strip().split())
    if not name or len(name) > 80:
        return None
    return name
