"""Finalize pass: every link a reply shows opens what the server can stand behind.

A link stays as written when its page was among this turn's search results or the chat's own
user messages (the words they typed, as link previews trust them), when it is the home page of
a site a result came from, when it is a Google Maps or Google search link (a search, not a
claim), or when it opens an app (``mailto:``, ``tel:``). A host written with no scheme
(``zunicafe.com``, ``www.…``) is read as https and held to the same.

A name the reply marked to look up, ``[Zuni Café](check "San Francisco")``, is the server's to
place (``name_links``): the name's own site from the results, Maps for a place, or a search.
Any other link with an address the server cannot stand behind (one the model wrote from memory,
a made-up source, ``#``) opens the name's own site when a result is on a host that names it,
and otherwise keeps only its words: no link and no search ("Read More" is no name to search).
A marked link that names nothing ("a taqueria"), a bare URL as its own words and a link on a
heading keep only their words too.

It runs after ``untrusted_media``, which turns a model's image into a link: the image's own
address is not a source claim, so those links stay. Fenced and inline code are copied as
written, so a code sample's links are untouched.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from app.modules.chat.inline_code import escaped_at, read_inline_code_span
from app.modules.chat.markdown_regions import map_prose_outside_fences
from app.modules.chat.name_links import Page, is_a_name, name_target, name_text, own_site
from app.services.prompt_safety import text_before_attachment_markers

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep import StreamContext

_USER_URL = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)
_IMAGE_SOURCE = re.compile(
    r"!\[[^\]\n]*\]\(\s*<?([^\s)>]+)|<img\b[^>]*\bsrc\s*=\s*[\"']?([^\"'\s>]+)", re.IGNORECASE
)
_GOOGLE_HOSTS = frozenset({"google.com", "maps.google.com"})
# Schemes that open an app, not a page: kept as written (``lib/linkSchemePolicy.ts``).
_APP_SCHEMES = frozenset({"mailto", "tel", "sms", "maps", "geo"})
# A host with no scheme: "zunicafe.com", "www.nopasf.com/menu".
_BARE_HOST = re.compile(r"^(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?$", re.IGNORECASE)
# The address the reply's model writes for a name it marks (``NAME_LINK_RULE``).
CHECK_MARKER = "check"
_TITLE_QUOTES = "\"'()"


def _key(url: str) -> tuple[str, str] | None:
    """Host (no ``www.``) and path (no trailing slash) with its query: what a link opens."""
    try:
        parts = urlsplit(url.strip().strip("<>"))
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    host = parts.hostname.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    return host, f"{path}?{parts.query}" if parts.query else path


class _Allowed:
    """The pages this turn may link: its results, the user's links and the model's images."""

    def __init__(self, urls: list[str]) -> None:
        keys = [key for url in urls if (key := _key(url)) is not None]
        self.pages = set(keys)
        self.hosts = {host for host, _path in keys}

    def __contains__(self, url: str) -> bool:
        key = _key(url)
        if key is None:
            return False
        host, path = key
        if key in self.pages or (path == "" and host in self.hosts):
            return True
        return host in _GOOGLE_HOSTS and (path.startswith("/maps") or path.startswith("/search"))


def link_reply_names(state: FinalizeState) -> str:
    """Pass entry: names open where the server says, and no link opens a made-up page."""
    ctx = state.ctx
    if state.server_text or "](" not in state.text:
        return state.text
    images = [next(g for g in match.groups() if g) for match in _IMAGE_SOURCE.finditer(state.raw)]
    pages = list(ctx.search_sources)
    allowed = _Allowed([hit.url for hit in pages] + _users_urls(ctx) + images)
    return place_links(state.text, allowed, pages)


def _users_urls(ctx: StreamContext) -> list[str]:
    """The URLs the user typed in this chat: this message and the earlier ones the turn read,
    their attachments' text left out (``text_before_attachment_markers``, as the phone's link
    previews read them). "Summarise https://…", then "what did it say about rents?" keeps
    the user's link in the second reply."""
    texts = [ctx.user_message_content or ""]
    for message in ctx.recent_messages or ():
        if getattr(message, "role", None) == "user":
            texts.append(str(getattr(message, "content", "") or ""))
    for message in ctx.prompt_messages:
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            texts.append(message["content"])
    return [
        url for text in texts for url in _USER_URL.findall(text_before_attachment_markers(text))
    ]


def place_links(text: str, allowed: _Allowed, pages: Sequence[Page]) -> str:
    if "](" not in text:
        return text
    placing = _Placing(allowed, pages)
    return map_prose_outside_fences(text, lambda prose: _rewrite_links(prose, placing))


def place_marks_only(text: str) -> str:
    """What stands in when the pass fails, and on a stopped reply's text: a marked name opens
    Maps or a search with no result to go by, and any other address the server cannot stand
    behind keeps only its words, so no raw ``check`` mark is ever saved."""
    return place_links(text, _Allowed([]), [])


class _Link:
    """An inline link: where it ends, its words, its address and its title."""

    def __init__(self, end: int, words: str, url: str, title: str) -> None:
        self.end = end
        self.words = words
        self.url = url
        self.title = title

    @property
    def marked(self) -> bool:
        """A name the reply's model marked to look up: ``check``, maybe ``check:City``."""
        url = self.url.casefold()
        return url == CHECK_MARKER or url.startswith(f"{CHECK_MARKER}:")

    @property
    def city(self) -> str:
        """The place's city a marked name gives, as its title or after ``check:``."""
        if not self.marked:
            return ""
        after = self.url[len(CHECK_MARKER) :].lstrip(":")
        return " ".join(f"{after} {self.title}".strip(_TITLE_QUOTES + " ").split())


def _link_at(prose: str, start: int) -> _Link | None:
    """The inline link whose ``[`` is at ``start``."""
    close = prose.find("]", start + 1)
    if close < 0 or "\n\n" in prose[start:close] or not prose.startswith("(", close + 1):
        return None
    depth = 0
    index = close + 1
    while index < len(prose):
        char = prose[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        elif char == "\n":
            return None
        index += 1
    else:
        return None
    target = prose[close + 2 : index].strip()
    url, _, title = target.partition(" ") if target else ("", "", "")
    title = title.strip().strip(_TITLE_QUOTES).strip()
    return _Link(index + 1, prose[start + 1 : close], url.strip("<>"), title)


def _plain(words: str) -> str:
    """A dropped link's words; a URL as its words becomes the site's name."""
    key = _key(words)
    return words if key is None else key[0]


def _on_heading(prose: str, at: int) -> bool:
    line_start = prose.rfind("\n", 0, at) + 1
    return prose[line_start:at].lstrip().startswith("#")


class _Placing:
    """One reply's links as the server places them: the pages it may open, and the names
    already linked (a name is linked the first time only: "Python Crash Course" came three
    times, linked each time, 2026-11-27)."""

    def __init__(self, allowed: _Allowed, pages: Sequence[Page]) -> None:
        self.allowed = allowed
        self.pages = pages
        self.linked: set[str] = set()

    def placed(self, prose: str, at: int, link: _Link) -> str:
        """The link as the reply keeps it."""
        if link.marked:
            return self._marked(prose, at, link)
        if _opens_an_app(link.url):
            return prose[at : link.end]
        url = _with_scheme(link.url)
        if url is not None and url in self.allowed:
            return prose[at : link.end] if url == link.url else f"[{link.words}]({url})"
        # An address no result gave: the name's own site from the results, else its words.
        name = name_text(link.words)
        site = None if _key(link.words) is not None else own_site(name, self.pages)
        return f"[{link.words}]({site})" if site is not None else _plain(link.words)

    def _marked(self, prose: str, at: int, link: _Link) -> str:
        name = name_text(link.words)
        if _key(link.words) is not None or _on_heading(prose, at) or not is_a_name(name):
            return _plain(link.words)
        if name.casefold() in self.linked:
            return link.words
        self.linked.add(name.casefold())
        return f"[{link.words}]({name_target(name, link.city, self.pages)})"


def _opens_an_app(url: str) -> bool:
    try:
        return urlsplit(url).scheme.lower() in _APP_SCHEMES
    except ValueError:
        return False


def _with_scheme(url: str) -> str | None:
    """``url`` as a web address: as written, or https for a host written with no scheme; None
    for anything else (``#``, a relative path, ``javascript:``)."""
    if _key(url) is not None:
        return url
    return f"https://{url}" if _BARE_HOST.match(url) else None


def _rewrite_links(prose: str, placing: _Placing) -> str:
    out: list[str] = []
    index = 0
    while index < len(prose):
        char = prose[index]
        if char == "`" and (code_end := read_inline_code_span(prose, index)) is not None:
            out.append(prose[index:code_end])
            index = code_end
            continue
        # An image's "[" opens its alt text, not a link.
        image = char == "!" and prose.startswith("[", index + 1)
        if char == "[" and not escaped_at(prose, index):
            link = _link_at(prose, index)
            if link is not None:
                out.append(placing.placed(prose, index, link))
                index = link.end
                continue
        out.append(prose[index : index + 2] if image else char)
        index += 2 if image else 1
    return "".join(out)
