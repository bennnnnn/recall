"""A message that works on the chat itself never searches the web; a live ask still does.

"Yes" to "Does that make sense? 😊" searched the band Yes; "sure give me a practice
problem" and "summarize what we covered" were wrapped in unrelated pages (2026-10-24).
The first draft skipped too much: a yes to "Want the full box score?" and "one more
question: what's the weather tomorrow?" stopped searching. Both sides are held here.
"""

from __future__ import annotations

import pytest

from app.gateways.web_search_gateway import WebSearchHit
from app.modules.web_search.source_quality import is_error_page

_PRIOR = ["an earlier question"]
_CHECK = "So V₂ = 2.34 L.\n\nDoes that make sense? 😊"


def _hit(title: str, snippet: str) -> WebSearchHit:
    return WebSearchHit(title=title, url="https://example.com/page", snippet=snippet)


@pytest.mark.parametrize(
    ("title", "snippet"),
    [
        # The live source chip.
        (
            "Weather API",
            "{'error': {'code': 2007, 'message': 'API key has reached maximum calls per "
            "month allowed limit.'}}",
        ),
        ("x", '{"message":"Unauthorized"}'),
        ("x", '{"detail":"Not found."}'),
        ("404 Not Found", ""),
        ("Error 403 - Forbidden", ""),
        ("401 Unauthorized", ""),
        ("429 Too Many Requests", ""),
        ("502 Bad Gateway", "502 Bad Gateway"),
        ("503 Service Temporarily Unavailable", ""),
        ("Just a moment...", ""),
        ("Attention Required! | Cloudflare", ""),
        ("x", "Checking your browser before accessing example.com."),
        ("x", "Sorry, you have been blocked"),
        ("x", "Access to this page has been denied."),
        ("x", "Please enable cookies."),
    ],
)
def test_an_error_page_is_no_source(title: str, snippet: str) -> None:
    assert is_error_page(_hit(title, snippet))


@pytest.mark.parametrize(
    ("title", "snippet"),
    [
        ("Forbidden City", "The Forbidden City is a palace complex in Beijing."),
        ("403(b) plans", "A 403(b) plan is a retirement plan for teachers and nonprofits."),
        ("API keys", "Authenticate requests by passing your API key in the header."),
        ("Rate limits", "The OpenAI API rate limit for GPT-4o is 30,000 tokens per minute."),
        ("reCAPTCHA", "reCAPTCHA is a free service that protects your site from spam."),
        ("HTTP 404 Not Found: what it means", "HTTP 404 Not Found means the page is gone."),
        ("Forbidden | Netflix", "A thriller about a forbidden love."),
        ("Paris weather", "Sunny, 18°C, light wind."),
    ],
)
def test_a_page_about_an_error_is_content(title: str, snippet: str) -> None:
    assert not is_error_page(_hit(title, snippet))
