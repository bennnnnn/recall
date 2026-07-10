"""Profile display helpers — shared name normalization for API updates."""


def normalize_display_name(raw: str | None) -> str | None:
    """Trim, collapse whitespace, and enforce length for user-visible names."""
    if raw is None:
        return None
    name = " ".join(raw.strip().split())
    if not name or len(name) > 80:
        return None
    return name


def user_location_label(user: object) -> str | None:
    """Device-synced city/region when the user has location enabled."""
    if not getattr(user, "location_enabled", False):
        return None
    text = str(getattr(user, "location", None) or "").strip()
    return text or None


def normalize_client_location(raw: str | None) -> str | None:
    """Trim and validate a one-shot location label from the client."""
    if raw is None:
        return None
    text = " ".join(str(raw).strip().split())
    if not text or len(text) > 200:
        return None
    return text


def normalize_client_coordinates(
    latitude: float | None,
    longitude: float | None,
) -> tuple[float, float] | None:
    """Validate paired GPS coordinates from the client."""
    if latitude is None and longitude is None:
        return None
    if latitude is None or longitude is None:
        return None
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return None
    return latitude, longitude


def effective_location_label(user: object, client_location: str | None = None) -> str | None:
    """Fresh client GPS label when location is enabled; otherwise profile city."""
    if not getattr(user, "location_enabled", False):
        return None
    normalized = normalize_client_location(client_location)
    if normalized:
        return normalized
    text = str(getattr(user, "location", None) or "").strip()
    return text or None
