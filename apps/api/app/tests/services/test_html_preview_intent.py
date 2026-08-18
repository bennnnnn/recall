import pytest

from app.core.config import Settings
from app.services.chat.prompt_constants import max_output_tokens_for_style
from app.services.chat.turn_prep.context import bump_max_out_for_html_preview
from app.services.html_preview_intent import is_html_preview_request


@pytest.mark.parametrize(
    "content, expected",
    [
        ("build a website", True),
        ("Make me a landing page for a coffee shop", True),
        ("create a dashboard to track expenses", True),
        ("design a login screen", True),
        ("build me an html page with a hero section", True),
        ("write html for a signup form", True),
        ("render a web mockup", True),
        ("build a web app", True),
        ("generate a portfolio site", True),
        ("draw me a website", False),  # image gen, not HTML
        ("paint a landing page", False),
        ("what is HTML?", False),
        ("explain photosynthesis", False),
        ("make a todo list", False),
        ("create a picture of a cat", False),
        ("I want a page about cats", False),  # generic "page" not a web noun
        ("", False),
        ("hello", False),
    ],
)
def test_is_html_preview_request(content: str, expected: bool) -> None:
    assert is_html_preview_request(content) is expected


def test_bump_raises_short_cap_to_detailed_for_html_preview() -> None:
    settings = Settings()
    short_cap = max_output_tokens_for_style("short", settings)
    max_out = bump_max_out_for_html_preview(short_cap, "build a website", settings)
    assert max_out == max(short_cap, max_output_tokens_for_style("detailed", settings))
    assert max_out >= 2200


def test_bump_raises_balanced_cap_to_detailed_for_html_preview() -> None:
    settings = Settings()
    balanced_cap = max_output_tokens_for_style("balanced", settings)
    max_out = bump_max_out_for_html_preview(balanced_cap, "make a landing page", settings)
    assert max_out == max(balanced_cap, max_output_tokens_for_style("detailed", settings))
    assert max_out >= 2200


def test_bump_leaves_cap_unchanged_for_non_html_turn() -> None:
    settings = Settings()
    short_cap = max_output_tokens_for_style("short", settings)
    max_out = bump_max_out_for_html_preview(short_cap, "explain photosynthesis", settings)
    assert max_out == short_cap


def test_bump_leaves_detailed_cap_unchanged() -> None:
    settings = Settings()
    detailed_cap = max_output_tokens_for_style("detailed", settings)
    max_out = bump_max_out_for_html_preview(detailed_cap, "build a website", settings)
    assert max_out == detailed_cap
