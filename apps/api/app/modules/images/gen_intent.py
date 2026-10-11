"""Detect composer image-generation intent (mirrors mobile imageGenIntent.ts).

The phone runs the same rules before it sends, so each helper has a same-named
TypeScript twin. Change both, and ``docs/fixtures/image_intent_cases.json``,
together; both test suites assert every case in that file.

Matching is linear token scans — no ``\\s+`` / ``.+`` regex on user chat text
(CodeQL ``py/polynomial-redos``).
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from app.modules.images.gen_intent_words import (
    ARTICLES,
    CODEISH_WORDS,
    DEICTIC_SUBJECTS,
    GENERATE_NOW_EXACT,
    IMAGE_NOUNS,
    MAKE_IDIOM_FILLER,
    MAKE_NOT_A_PICTURE,
    NON_IMAGE_DRAW_WORDS,
    NON_IMAGE_WORDS,
    NON_REVISION,
    NOT_REVISION_STARTERS,
    NOUN_MESSAGE_FILE_WORDS,
    NOUN_ONLY_FILLER,
    POSSESSIVES,
    REACTION_PHRASES,
    REACTION_WORDS,
    REVISION_PRONOUNS,
    SHOW_NON_IMAGE_WORDS,
    SHOW_REVISION_TARGETS,
    SUBJECTLESS_FILLER,
    VERBS_DRAW,
    VERBS_IMAGE,
)

_USER_MESSAGE_PREFIX = "Generate image: "


def _tokens(text: str) -> list[str]:
    """Whitespace-split only — linear in ``len(text)``."""
    return text.split()


def _strip_polite(tokens: list[str]) -> list[str]:
    i = 0
    n = len(tokens)
    if i < n and tokens[i].lower() == "please":
        i += 1
    if i + 1 < n and tokens[i].lower() == "can" and tokens[i + 1].lower() == "you":
        i += 2
    return tokens[i:]


def _join_subject(parts: list[str]) -> str:
    return " ".join(parts).strip()


def _clean_prompt(raw: str) -> str | None:
    prompt = raw.strip().rstrip(".!?").strip()
    if not prompt or len(prompt) < 2:
        return None
    if any(_fold_token(w) in CODEISH_WORDS for w in prompt.split()):
        return None
    return prompt


def _fold_token(word: str) -> str:
    """Lowercase and strip edge punctuation so ``tips,`` matches ``tips``."""
    return word.lower().strip(".,!?;:\"'()[]")


def _has_non_image_subject(subject: str) -> bool:
    words = subject.split()
    for i, word in enumerate(words):
        key = _fold_token(word)
        if key in NON_IMAGE_WORDS:
            return True
        nxt = _fold_token(words[i + 1]) if i + 1 < len(words) else ""
        if key == "pull" and nxt in {"request", "requests"}:
            return True
    return False


def _has_non_image_draw(subject: str) -> bool:
    words = [_fold_token(word) for word in subject.split()]
    if "sketch of the idea" in " ".join(words):
        return True
    return any(word in NON_IMAGE_DRAW_WORDS for word in words)


def _names_no_subject(parts: list[str]) -> bool:
    """``the image`` / ``just a pic of`` — only fillers and image nouns, no subject."""
    return all(
        _fold_token(tok) in IMAGE_NOUNS or _fold_token(tok) in SUBJECTLESS_FILLER for tok in parts
    )


_MAX_IMAGE_MODIFIERS = 3


def _match_verb_then_image(tokens: list[str]) -> str | None:
    """create/generate … image/pic … of? SUBJECT

    A few words may describe the picture first (``create a realistic photo of
    a dog``); they stay in the prompt, so the subject must follow ``of``.
    """
    if len(tokens) < 3:
        return None
    if tokens[0].lower() not in VERBS_IMAGE:
        return None
    i = 1
    if i < len(tokens) and tokens[i].lower() == "me":
        i += 1
    if i < len(tokens) and tokens[i].lower() in ARTICLES:
        i += 1
    start = i
    while (
        i < len(tokens)
        and i - start < _MAX_IMAGE_MODIFIERS
        and tokens[i].lower() not in IMAGE_NOUNS
    ):
        i += 1
    if i >= len(tokens) or tokens[i].lower() not in IMAGE_NOUNS:
        return None
    if i > start:
        rest = tokens[i + 2 :]
        if rest and rest[0].lower() in ARTICLES:
            rest = rest[1:]
        if not rest or tokens[i + 1].lower() != "of":
            return None
        i = start
    else:
        i += 1
        if i < len(tokens) and tokens[i].lower() == "of":
            i += 1
    if i >= len(tokens):
        return None
    subject = _join_subject(tokens[i:])
    if _has_non_image_subject(subject) or _has_non_image_draw(subject):
        return None
    return _clean_prompt(subject)


def _match_verb_subject_image(tokens: list[str]) -> str | None:
    """create/generate … SUBJECT image/pic/photo"""
    if len(tokens) < 3:
        return None
    if tokens[0].lower() not in VERBS_IMAGE:
        return None
    if tokens[-1].lower() not in IMAGE_NOUNS:
        return None
    i = 1
    if i < len(tokens) - 1 and tokens[i].lower() == "me":
        i += 1
    if i < len(tokens) - 1 and tokens[i].lower() in ARTICLES:
        i += 1
    subject_parts = tokens[i:-1]
    if not subject_parts or _names_no_subject(subject_parts):
        return None
    subject = _join_subject(subject_parts)
    if _has_non_image_subject(subject) or _has_non_image_draw(subject):
        return None
    return _clean_prompt(subject)


def _match_draw_me(tokens: list[str]) -> str | None:
    """draw/paint/illustrate me [a/an] SUBJECT"""
    if len(tokens) < 3:
        return None
    if tokens[0].lower() not in VERBS_DRAW:
        return None
    if tokens[1].lower() != "me":
        return None
    i = 2
    if i < len(tokens) and tokens[i].lower() in ARTICLES:
        i += 1
    if i >= len(tokens):
        return None
    subject = _join_subject(tokens[i:])
    if _has_non_image_subject(subject) or _has_non_image_draw(subject):
        return None
    return _clean_prompt(subject)


def _make_is_not_a_picture(subject: str) -> bool:
    words = [_fold_token(word) for word in subject.split()]
    words = [word for word in words if word and word not in MAKE_IDIOM_FILLER]
    return bool(words) and all(word in MAKE_NOT_A_PICTURE for word in words)


def _match_short_create(tokens: list[str]) -> str | None:
    """Short ``draw a dog`` or ``create a cat`` — the whole message is the subject.

    Chat asks such as ``make your own example`` still fail ``_has_non_image_subject``.
    ``make money`` is not a picture; ``make a cat photo`` is matched earlier.
    """
    if len(tokens) < 2:
        return None
    verb = tokens[0].lower()
    if verb not in VERBS_DRAW and verb not in VERBS_IMAGE:
        return None
    i = 1
    if i < len(tokens) and tokens[i].lower() == "me":
        i += 1
    if i < len(tokens) and tokens[i].lower() in ARTICLES:
        i += 1
    subject_parts = tokens[i:]
    if not subject_parts or len(subject_parts) > 8:
        return None
    if subject_parts[0].lower() in REVISION_PRONOUNS:
        return None
    # "create an image" names no subject; the thread may supply one.
    if _names_no_subject(subject_parts):
        return None
    subject = _join_subject(subject_parts)
    if verb == "make" and _make_is_not_a_picture(subject):
        return None
    if _has_non_image_subject(subject) or _has_non_image_draw(subject):
        return None
    return _clean_prompt(subject)


def _match_image_noun_message(tokens: list[str]) -> str | None:
    """Short colloquial ask: ``cat pic`` / ``a sunset photo`` / ``photo of a cat``.

    The image noun must close the message, or open it before ``of``. A noun in
    the middle (``best photo editing apps``, ``picture this``) is ordinary chat,
    and so is a question or a possessive (``how to take a good photo``).
    """
    if len(tokens) < 2 or len(tokens) > 16:
        return None
    folded = [_fold_token(tok) for tok in tokens]
    if folded[-1] in IMAGE_NOUNS:
        parts = tokens[:-1]
    else:
        i = 1 if folded[0] in ARTICLES else 0
        if i + 1 >= len(tokens) or folded[i] not in IMAGE_NOUNS or folded[i + 1] != "of":
            return None
        parts = tokens[i + 2 :]
    if parts and _fold_token(parts[0]) in ARTICLES:
        parts = parts[1:]
    if not parts or _names_no_subject(parts):
        return None
    first = _fold_token(parts[0])
    if (
        first in POSSESSIVES
        or first in NOT_REVISION_STARTERS
        or first in IMAGE_NOUNS
        or first in VERBS_IMAGE
        or first in VERBS_DRAW
    ):
        return None
    subject = _join_subject(parts)
    if any(_fold_token(w) in NOUN_MESSAGE_FILE_WORDS for w in parts):
        return None
    if _has_non_image_subject(subject) or _has_non_image_draw(subject):
        return None
    return _clean_prompt(subject)


def extract_image_gen_prompt(text: str) -> str | None:
    """Return the image subject if ``text`` is a clear image-gen ask, else None."""
    from app.services.subject_scan import is_scanner_camera_prompt

    trimmed = text.strip()
    if not trimmed or len(trimmed) > 500:
        return None
    # Scanner captions contain "image" and are often ≤80 chars, which the
    # short image-noun heuristic would steal as a generate-image ask.
    if is_scanner_camera_prompt(trimmed):
        return None

    if trimmed.lower().startswith(_USER_MESSAGE_PREFIX.lower()):
        return _clean_prompt(trimmed[len(_USER_MESSAGE_PREFIX) :])

    tokens = _strip_polite(_tokens(trimmed))
    if not tokens:
        return None

    matched = _match_verb_then_image(tokens)
    if matched:
        return matched

    matched = _match_verb_subject_image(tokens)
    if matched:
        return matched

    matched = _match_draw_me(tokens)
    if matched:
        return matched

    # Short create/draw only when the whole message is short (same as before).
    if len(trimmed) <= 80:
        matched = _match_short_create(tokens)
        if matched:
            return matched
        matched = _match_image_noun_message(tokens)
        if matched:
            return matched

    return None


def is_image_noun_only_message(text: str) -> bool:
    """True for a bare image ask with no subject: ``Image``, ``a pic``, ``create an image``."""
    if is_image_gen_generate_now(text):
        return False
    tokens = _strip_polite(_tokens(text.strip().rstrip(".!?")))
    if tokens and (tokens[0].lower() in VERBS_IMAGE or tokens[0].lower() in VERBS_DRAW):
        tokens = tokens[1:]
        if tokens and tokens[0].lower() == "me":
            tokens = tokens[1:]
    kept = [tok for tok in tokens if tok.lower() not in NOUN_ONLY_FILLER]
    if not kept:
        return False
    return all(tok.lower() in IMAGE_NOUNS for tok in kept)


def is_image_gen_generate_now(text: str) -> bool:
    """True when this line is 'do it' / 'that works' / 'u pick' after a scene."""
    collapsed = " ".join(text.strip().lower().split()).rstrip(".!?").strip()
    if not collapsed or len(collapsed) > 40:
        return False
    if collapsed in GENERATE_NOW_EXACT:
        return True
    padded = f" {collapsed} "
    return " do it " in padded or " u do it " in padded or " you do it " in padded


def could_be_image_thread_followup(text: str) -> bool:
    """True if this line might complete a prior 'dog' + 'image' thread.

    Used to skip the Neon recent-message lookup when the text cannot be a
    follow-up even with prior subject context.
    """
    return is_image_noun_only_message(text) or is_image_gen_generate_now(text)


def _thread_subject_from_user(text: str) -> str | None:
    """Prior user line usable as a generate subject (short concrete noun)."""
    trimmed = text.strip()
    if not trimmed or len(trimmed) > 80 or "?" in trimmed:
        return None
    if is_image_noun_only_message(trimmed) or is_image_gen_generate_now(trimmed):
        return None
    existing = extract_image_gen_prompt(trimmed)
    if existing:
        return existing
    words = trimmed.split()
    if not words or len(words) > 6:
        return None
    first = words[0].lower().rstrip(".!,")
    if first in NOT_REVISION_STARTERS:
        return None
    if _has_non_image_subject(trimmed) or _has_non_image_draw(trimmed):
        return None
    cleaned = _clean_prompt(trimmed)
    if not cleaned or cleaned.lower() in NON_REVISION:
        return None
    return cleaned


def prior_user_contents_for_image_gen(messages: list[Any], current: str) -> list[str]:
    """Oldest-first user bodies, excluding the in-flight current line if present."""
    current_stripped = current.strip()
    out: list[str] = []
    for row in messages:
        role = getattr(row, "role", None)
        content = getattr(row, "content", None)
        if role is None and isinstance(row, dict):
            role = row.get("role")
            content = row.get("content")
        if role != "user" or not isinstance(content, str):
            continue
        out.append(content)
    if out and out[-1].strip() == current_stripped:
        out.pop()
    return out


def _is_deictic_subject(subject: str) -> bool:
    first = _fold_token(subject.split()[0]) if subject.split() else ""
    return first in DEICTIC_SUBJECTS


def _resolve_deictic_subject(direct: str, prior_user_contents: list[str]) -> str:
    if not _is_deictic_subject(direct):
        return direct
    for prior in reversed(prior_user_contents):
        subject = extract_image_gen_prompt(prior)
        if subject and not _is_deictic_subject(subject):
            return subject
    return direct


def extract_image_gen_prompt_from_thread(
    text: str,
    prior_user_contents: list[str],
) -> str | None:
    """Same as ``extract_image_gen_prompt``, plus 'Dog' then 'Image' follow-ups.

    A picture of "that car" uses the previous concrete subject.
    Mirrors mobile ``extractImageGenPromptFromThread``.
    """
    direct = extract_image_gen_prompt(text)
    if direct:
        return _resolve_deictic_subject(direct, prior_user_contents)
    if is_image_noun_only_message(text):
        for prior in reversed(prior_user_contents):
            subject = _thread_subject_from_user(prior)
            if subject:
                return subject
        return None
    if not is_image_gen_generate_now(text):
        return None
    return _subject_from_active_image_exchange(prior_user_contents)


def _subject_from_active_image_exchange(prior_user_contents: list[str]) -> str | None:
    """Confirm ("do it") only against the current image exchange, not any older ask."""
    skipped_noun_only = False
    for prior in reversed(prior_user_contents):
        if is_image_gen_generate_now(prior):
            continue
        if is_image_noun_only_message(prior):
            skipped_noun_only = True
            continue
        explicit = extract_image_gen_prompt(prior)
        if explicit:
            return explicit
        if skipped_noun_only:
            return _thread_subject_from_user(prior)
        return None
    return None


def _is_reaction(text: str) -> bool:
    collapsed = " ".join(text.strip().lower().split()).rstrip(".!?").strip()
    if collapsed.startswith("please "):
        collapsed = collapsed[len("please ") :].strip()
    if not collapsed:
        return False
    if collapsed in REACTION_PHRASES:
        return True
    return collapsed.split()[0] in REACTION_WORDS


def _has_edit_lead_in(tokens: list[str]) -> bool:
    i = 0
    n = len(tokens)
    if i < n and tokens[i].lower() == "please":
        i += 1
    if i + 1 < n and tokens[i].lower() == "make" and tokens[i + 1].lower() in {"it", "them"}:
        return True
    if i + 1 < n and tokens[i].lower() == "change" and tokens[i + 1].lower() in {"it", "them"}:
        return True
    return i < n and tokens[i].lower() in {"now", "again", "instead", "try"}


_SHOW_NON_IMAGE_SYMBOLS = "+-\u00d7\u00f7*/=^"


def _is_show_image_revision(tokens: list[str]) -> bool:
    if len(tokens) < 3 or tokens[0].lower() != "show":
        return False
    if any(symbol in tok for tok in tokens for symbol in _SHOW_NON_IMAGE_SYMBOLS):
        return False
    words = [_fold_token(tok) for tok in tokens]
    if any(word in SHOW_NON_IMAGE_WORDS for word in words):
        return False
    if any(a == "long" and b == "division" for a, b in pairwise(words)):
        return False
    return words[1] in SHOW_REVISION_TARGETS


def subject_from_image_gen_user_message(content: str) -> str | None:
    """Subject from a prior image-gen user bubble (legacy prefix or natural wording)."""
    trimmed = content.strip()
    if trimmed.lower().startswith(_USER_MESSAGE_PREFIX.lower()):
        return _clean_prompt(trimmed[len(_USER_MESSAGE_PREFIX) :])
    return extract_image_gen_prompt(trimmed)


def is_image_only_assistant_content(content: str) -> bool:
    """True when the assistant bubble is only an ``[Image: …]`` marker."""
    has_image = False
    for line in content.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("[Image:") and s.endswith("]") and len(s) > len("[Image:]"):
            has_image = True
            continue
        return False
    return has_image


def _strip_revision_lead_in(tokens: list[str]) -> list[str]:
    """Drop ``make it`` / ``change them to`` / ``now`` style lead-ins (linear)."""
    i = 0
    n = len(tokens)
    if i < n and tokens[i].lower() == "please":
        i += 1
    if (
        i + 1 < n
        and tokens[i].lower() == "make"
        and tokens[i + 1].lower()
        in {
            "it",
            "them",
        }
    ):
        return tokens[i + 2 :]
    if (
        i + 1 < n
        and tokens[i].lower() == "change"
        and tokens[i + 1].lower()
        in {
            "it",
            "them",
        }
    ):
        j = i + 2
        if j < n and tokens[j].lower() == "to":
            j += 1
        return tokens[j:]
    if i < n and tokens[i].lower() in {"now", "again", "instead", "try"}:
        return tokens[i + 1 :]
    return tokens[i:]


def extract_image_revision_prompt(
    text: str,
    *,
    last_assistant_is_image_only: bool,
    previous_subject: str | None,
) -> str | None:
    """Short follow-up after an image-only reply → new generate prompt."""
    if not last_assistant_is_image_only or not previous_subject:
        return None
    trimmed = text.strip()
    if not trimmed or len(trimmed) > 120:
        return None
    if not _has_edit_lead_in(_tokens(trimmed)) and _is_reaction(trimmed):
        return None

    tokens = _strip_revision_lead_in(_tokens(trimmed))
    if not tokens or len(tokens) > 8:
        return None
    if "?" in trimmed:
        return None
    first = tokens[0].lower().rstrip(".!,")
    if first in NOT_REVISION_STARTERS and not _is_show_image_revision(tokens):
        return None
    revision = _join_subject(tokens)
    if not revision:
        return None
    if _has_non_image_subject(revision):
        return None
    cleaned = _clean_prompt(revision)
    if not cleaned:
        return None
    if cleaned.lower() in NON_REVISION:
        return None
    return f"{previous_subject}, {cleaned}"


def could_be_image_revision(text: str) -> bool:
    """True if this text could revise a prior image-only reply.

    Used to skip the Neon recent-message lookup when the text cannot be a
    revision even if the last assistant was image-only (greetings, thanks).
    """
    return (
        extract_image_revision_prompt(
            text,
            last_assistant_is_image_only=True,
            previous_subject="x",
        )
        is not None
    )


def image_gen_revision_context(
    messages: list[Any],
) -> tuple[bool, str | None]:
    """Walk newest→oldest for image-gen context used by revision intercept."""
    last_assistant_is_image_only = False
    previous_subject: str | None = None
    for row in reversed(messages):
        role = getattr(row, "role", None)
        content = getattr(row, "content", None)
        if role is None and isinstance(row, dict):
            role = row.get("role")
            content = row.get("content")
        if not isinstance(content, str):
            content = ""
        if not last_assistant_is_image_only and role == "assistant":
            model = getattr(row, "model", None)
            if model is None and isinstance(row, dict):
                model = row.get("model")
            # Reference-photo lookup is image-only content but must not be
            # treated as an AI-image revision target.
            if model == "image-search-model":
                break
            last_assistant_is_image_only = is_image_only_assistant_content(content)
            if not last_assistant_is_image_only:
                break
            continue
        if last_assistant_is_image_only and role == "user":
            previous_subject = subject_from_image_gen_user_message(content) or "the provided image"
            break
    return last_assistant_is_image_only, previous_subject
