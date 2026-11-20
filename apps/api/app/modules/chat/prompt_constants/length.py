"""How long a reply should be: what the user's own message asks for.

There is no account-wide length setting (FEATURES.md, Personalization): each message
sets its own ("in one sentence", "in detail"). ``reply_length`` reads one text; a plan
that splits a message into parts calls it once per part. ``STYLE_HINTS`` holds the
length line a turn's system prompt carries.
"""

BREVITY_REQUEST_HINT = (
    "The user set the length: a sentence, word or line count, or a brief answer. "
    "Ignore decorative table/heading layout and match the length they asked exactly. Preserve a "
    "draft/code/visual container only when that container is the requested deliverable. "
    "When shortening existing text, never drop or blur factual details such as units, "
    "quantities, dates, names, or commitments."
)


MIXED_LENGTH_HINT = (
    "The user set different lengths for different parts of this message (one sentence for "
    "one question, detail for another). Give each part exactly the length it asked for; a "
    "one-sentence part stays one sentence."
)


def many_parts_hint(parts: int, max_output_tokens: int) -> str:
    """Said beside a message with ``turn_reading.length.MANY_PARTS`` asks or more: one reply
    may not hold them all, so it says up front what it covers and what it can't do here."""
    # Worked maths costs about 2.5 characters a token, so the cap is ~3/8 of it in words.
    words = max(500, round(max_output_tokens * 3 / 8, -2))
    return (
        f"This message asks {parts} separate things. One reply has room for about "
        f"{words:,.0f} words, so they may not all fit in full. If they won't, open with one "
        "or two lines saying which parts this reply answers and which it leaves for a "
        "follow-up, and name any part you can't do here (running code, a numerical "
        "simulation or integration, a plot or file this chat can't produce), with what you "
        "give instead: the method, the equations to integrate, what the result would show. "
        "Then answer the parts you named fully, in the message's order, never stopping "
        "partway through one, and end by offering to go on with the rest. If they all fit, "
        "answer every part."
    )


# The length line of the system prompt: SHORT on a greeting or an ack (the lightweight
# path), DETAILED when the message asked for depth, otherwise fit to the question.
STYLE_HINTS = {
    "short": (
        "Response length: SHORT. Answer in one to three sentences. No preamble, no recap of "
        "the question, no closing offer to help further. No sections, headings, tables, "
        "diagrams, or HTML unless the user asked for them."
    ),
    "balanced": (
        "Response length: fit the question. A simple question gets a short, direct answer; a "
        "hard, technical or multi-part one gets the depth it needs, without padding. Use short "
        "headings and bullets only when they help. Lead with the answer (a calculation "
        "leads with its working); explanation after."
    ),
    "detailed": (
        "Response length: DETAILED. The user asked for depth: explain fully, with the "
        "mechanism, reasoning, examples, edge cases and trade-offs that matter. Stay "
        "scannable, with headings and lists where they fit; a requested essay, story, letter "
        "or paragraph keeps its prose form."
    ),
}
