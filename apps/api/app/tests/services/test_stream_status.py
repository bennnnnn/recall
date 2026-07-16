"""Stream status helpers."""

from app.services.chat.stream_status import (
    STATUS_DETAIL_MAX_CHARS,
    STREAM_STATUS_PHASES,
    clip_status_detail,
)


def test_phases_include_activity_specific_entries():
    for phase in ("remembering", "reading_files", "searching", "calculating"):
        assert phase in STREAM_STATUS_PHASES


def test_clip_status_detail_flattens_whitespace():
    assert clip_status_detail("  weather \n in   berlin ") == "weather in berlin"


def test_clip_status_detail_none_and_blank():
    assert clip_status_detail(None) is None
    assert clip_status_detail("   \n ") is None


def test_clip_status_detail_bounds_length():
    clipped = clip_status_detail("a" * 500)
    assert clipped is not None
    assert len(clipped) <= STATUS_DETAIL_MAX_CHARS
    assert clipped.endswith("…")
