"""Finalize pass: every link a reply shows opens what the server can stand behind.

Only a web link is this pass's: a name the reply marked to look up (``check``, maybe
``check "City"`` or ``check:City``), an ``http(s)`` address, or a host written from ``www.``.
Any other ``[…](…)`` (``#``, ``mailto:``, a relative path) is left exactly as written, and so is
every ``[…](…)`` inside maths (``$…$``, ``$$…$$``, ``\\(…\\)``, ``\\[…\\]``, read as the phone reads
them: ``$\\mathcal{L}[t^2](s)$``, ``$[A](t)$``), inline code and fences.

A web link stays as written when its page was among this turn's search results, the chat's own
user messages (the words they typed, as link previews trust them) or the links the chat's
earlier replies already carried, when it is the home page of a site a result came from, or when
it is a Google Maps or Google search link (a search, not a claim). A ``www.`` host is read as
https and held to the same.

A name the reply marked to look up, ``[Zuni Café](check "San Francisco")``, is the server's to
place (``name_links``): the name's own site from the results, Maps for a place, or a search. A
web address the server cannot stand behind (one the model wrote from memory, a made-up source)
opens the name's own site when a result is on a host that names it, and otherwise keeps only
its words: no link and no search ("Read More" is no name to search). A marked link that names
nothing ("a taqueria"), a bare URL as its own words, a link on a heading and a name's second
mark keep only their words too, and a mark inside a fence (a steps card, a draft) keeps its
words: no raw ``check`` is ever saved, and the phone draws one only as words while it streams.

It runs after ``untrusted_media``, which turns a model's image into a link: the image's own
address is not a source claim, so those links stay.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from app.modules.chat.display_dollars import display_dollar_pair_end
from app.modules.chat.inline_code import escaped_at, read_inline_code_span
from app.modules.chat.markdown_regions import map_prose_outside_fences
from app.modules.chat.math_padding import maths_pair_end
from app.modules.chat.name_links import Page, is_a_name, name_target, name_text, own_site
from app.services.md_fence_scan import iter_fences
from app.services.prompt_safety import text_before_attachment_markers

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep import StreamContext

_USER_URL = re.compile(r"https?://[^\s<>()\[\]\"']+", re.IGNORECASE)
# A link an earlier reply carried: "](https://…)".
_REPLY_LINK = re.compile(r"\]\(\s*<?(https?://[^\s)>]+)", re.IGNORECASE)
_IMAGE_SOURCE = re.compile(
    r"!\[[^\]\n]*\]\(\s*<?([^\s)>]+)|<img\b[^>]*\bsrc\s*=\s*[\"']?([^\"'\s>]+)", re.IGNORECASE
)
_GOOGLE_HOSTS = frozenset({"google.com", "maps.google.com"})
# A host written from "www." with no scheme: "www.nopasf.com/menu".
_WWW_HOST = re.compile(r"^www\.[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?$", re.IGNORECASE)
# The address the reply's model writes for a name it marks (``NAME_LINK_RULE``).
CHECK_MARKER = "check"
# A marked link inside a fence, its title's one pair of brackets included.
_FENCED_MARK = re.compile(
    r"(?<!!)\[([^\]\n]+)\]\(\s*check(?=[\s:)\"'])(?:[^()\n]|\([^()\n]*\))*\)", re.IGNORECASE
)
# The pairs a link title may stand between.
_TITLE_PAIRS = (('"', '"'), ("'", "'"), ("(", ")"))


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
    """The pages this turn may link: its results, the user's links, the chat's earlier
    replies' links and the model's images."""

    def __init__(self, urls: Iterable[str]) -> None:
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
    allowed = _Allowed([hit.url for hit in pages] + _chat_urls(ctx) + images)
    return place_links(state.text, allowed, pages)


def _chat_messages(ctx: StreamContext) -> list[tuple[str, str]]:
    """The chat's messages the turn read, as (role, text): the stored window and the prompt's."""
    messages = [("user", ctx.user_message_content or "")]
    for message in ctx.recent_messages or ():
        role = getattr(message, "role", None)
        messages.append((str(role), str(getattr(message, "content", "") or "")))
    for message in ctx.prompt_messages:
        content = message.get("content")
        if isinstance(content, str):
            messages.append((str(message.get("role")), content))
    return messages


def _chat_urls(ctx: StreamContext) -> list[str]:
    """The URLs the user typed in this chat (their attachments' text left out, as the phone's
    link previews read them) and the links the chat's earlier replies carried: "Summarise
    https://…", then "what did it say about rents?" keeps the user's link, and "which of those
    is best for a date?" keeps the site an earlier search gave Zuni Café."""
    urls: list[str] = []
    for role, text in _chat_messages(ctx):
        if role == "user":
            urls += _USER_URL.findall(text_before_attachment_markers(text))
        elif role == "assistant":
            urls += _REPLY_LINK.findall(text)
    return urls


def place_links(text: str, allowed: _Allowed, pages: Sequence[Page]) -> str:
    if "](" not in text:
        return text
    placing = _Placing(allowed, pages)
    placed = map_prose_outside_fences(text, lambda prose: _rewrite_links(prose, placing))
    return _fence_marks_as_words(placed) if "](" in placed else placed


def place_marks_only(text: str) -> str:
    """What stands in when the pass fails, and on a stopped reply's text: a marked name opens
    Maps or a search with no result to go by, and any other web address the server cannot
    stand behind keeps only its words, so no raw ``check`` mark is ever saved."""
    return place_links(text, _Allowed([]), [])


def _fence_marks_as_words(text: str) -> str:
    """Each fence (a steps card, a draft) as written, every ``check`` mark in it its words: a
    card reads no links, and a draft is copied."""
    pieces: list[str] = []
    cursor = 0
    for fence in iter_fences(text):
        body = text[fence.body_start : fence.body_end]
        if "](" not in body:
            continue
        pieces += [text[cursor : fence.body_start], _FENCED_MARK.sub(lambda m: m.group(1), body)]
        cursor = fence.body_end
    return "".join([*pieces, text[cursor:]])


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
    def web(self) -> bool:
        """This pass's link: a mark, an http(s) address or a ``www.`` host."""
        return self.marked or _key(self.url) is not None or _WWW_HOST.match(self.url) is not None

    @property
    def city(self) -> str:
        """The place's city a marked name gives, as its title or after ``check:``."""
        if not self.marked:
            return ""
        after = self.url[len(CHECK_MARKER) :].lstrip(":")
        return " ".join(f"{after} {self.title}".split())


def _unquoted(title: str) -> str:
    """A link title without the one pair of quotes or brackets it stands between: "New York
    (Greenwich Village)" keeps its own brackets."""
    title = title.strip()
    for opening, closing in _TITLE_PAIRS:
        if len(title) >= 2 and title.startswith(opening) and title.endswith(closing):
            return title[1:-1].strip()
    return title


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
    return _Link(index + 1, prose[start + 1 : close], url.strip("<>"), _unquoted(title))


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
        if not link.web:
            return prose[at : link.end]
        if link.marked:
            return self._marked(prose, at, link)
        url = link.url if _key(link.url) is not None else f"https://{link.url}"
        if url in self.allowed:
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


def _maths_end(prose: str, index: int) -> int | None:
    """The end of the maths that opens at ``index`` (``$…$``, ``$$…$$``, ``\\(…\\)``,
    ``\\[…\\]``), read as the phone reads it (``display_dollars``, ``math_padding``); None when
    no maths opens there."""
    if prose.startswith("$$", index):
        return display_dollar_pair_end(prose, index)
    if prose.startswith("$", index):
        line_start = prose.rfind("\n", 0, index) + 1
        line_end = prose.find("\n", index)
        line = prose[line_start : len(prose) if line_end < 0 else line_end]
        end = maths_pair_end(line, index - line_start)
        return None if end is None else line_start + end
    for opener, closer in (("\\(", "\\)"), ("\\[", "\\]")):
        if prose.startswith(opener, index) and not escaped_at(prose, index):
            close = prose.find(closer, index + 2)
            return None if close < 0 else close + 2
    return None


def _rewrite_links(prose: str, placing: _Placing) -> str:
    out: list[str] = []
    index = 0
    while index < len(prose):
        char = prose[index]
        if char == "`" and (code_end := read_inline_code_span(prose, index)) is not None:
            out.append(prose[index:code_end])
            index = code_end
            continue
        if char in "$\\" and (maths_end := _maths_end(prose, index)) is not None:
            out.append(prose[index:maths_end])
            index = maths_end
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
