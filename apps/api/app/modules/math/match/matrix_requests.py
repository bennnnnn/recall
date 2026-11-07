"""Which results one matrix question asks for: "the determinant and inverse of [[2,1],[5,3]]".

``matrix_signal`` names one operation. A question that lists several (determinant and
inverse, rank and transpose, eigenvalues and eigenvectors) wants every one of them, and a
question that applies one to another's result ("the inverse of the transpose of …") wants
neither of them on its own: that is a composition, and the reader declines it.
"""

from __future__ import annotations

import re

from app.modules.math.schemas.operations import MatrixOp
from app.services.text_match import word_index

# Each operation a single matrix can be asked, with the words that name it. A word is
# matched at a word start; the ones in ``_WHOLE`` must be whole words ("rank", "det").
_CUES: tuple[tuple[MatrixOp, tuple[str, ...]], ...] = (
    ("determinant", ("determinant", "det")),
    ("inverse", ("inverse",)),
    ("transpose", ("transpose",)),
    ("rank", ("rank",)),
    ("rref", ("rref", "reduced row echelon", "row echelon")),
    ("eigenvectors", ("eigenvector",)),
    ("eigenvalues", ("eigenvalue",)),
    ("nullspace", ("nullspace", "null space", "kernel")),
    ("columnspace", ("column space", "columnspace", "colspace")),
    ("rowspace", ("row space", "rowspace")),
    ("diagonalize", ("diagonaliz", "diagonalis")),
)
_WHOLE = frozenset({"det", "rank", "kernel"})
# Two matrices or an operation between them: the single-operation reader owns these.
_BINARY_WORDS = ("multiply", "times", "product", "add", "plus")
SQUARE_OPS = frozenset({"determinant", "inverse", "eigenvalues", "eigenvectors", "diagonalize"})


def _starts(lower: str, cue: str) -> list[int]:
    """Every place ``cue`` starts a word (the ``_WHOLE`` ones as whole words)."""
    spots: list[int] = []
    at = lower.find(cue)
    while at != -1:
        after = at + len(cue)
        whole = cue not in _WHOLE or after >= len(lower) or not lower[after].isalpha()
        if (at == 0 or not lower[at - 1].isalpha()) and whole:
            spots.append(at)
        at = lower.find(cue, at + 1)
    return spots


def _first_at(lower: str, cue: str) -> int:
    """Where ``cue`` first starts a word (``det`` also as ``det(``), or -1."""
    spots = _starts(lower, cue)
    return spots[0] if spots else -1


_OP_WORDS = "|".join(re.escape(cue) for _, cues in _CUES for cue in cues)
# One operation applied to another's result: "the determinant of the inverse", "the
# eigenvalues ... and of its inverse", "the inverse of that", "A times its inverse".
# "Of this matrix [[…]]" and "the determinant and its inverse" are about A itself.
_COMPOSED = re.compile(
    rf"\bof\s+(?:the|its|this|that)\s+(?:{_OP_WORDS})"
    r"|\bof\s+(?:that|this|it)\b(?!\s*(?:matrix|\[\[))"
    r"|\bof\s+the\s+(?:result|answer)\b"
    rf"|(?:\btimes|\bmultiplied\s+by|\bplus|\bminus|[*\u00d7+-])\s*(?:its|the)\s+(?:{_OP_WORDS})"
)
# The one matrix inside arithmetic: "[[…]] * 2", "2[[…]]", "[[…]]^2".
_IN_ARITHMETIC = re.compile(r"\]\]\s*[*\u00d7+\-/^]|[*\u00d7+\-/^]\s*\[\[|\d\s*\[\[")
# An operation named as the method, not as a result: "without computing the
# determinant", "use the determinant to find …", "by row reduction".
_AS_METHOD = re.compile(
    r"\b(?:without|not|use|using|by|via)\s+(?:\w+ing\s+)?(?:the\s+|its\s+|a\s+)?$"
)


def _asked(lower: str) -> list[MatrixOp]:
    """Each operation asked for as a result, in the order the question first asks it."""
    found: list[tuple[int, MatrixOp]] = []
    for op, cues in _CUES:
        spots = [
            at
            for cue in cues
            for at in _starts(lower, cue)
            if not _AS_METHOD.search(lower[max(0, at - 40) : at])
        ]
        if spots:
            found.append((min(spots), op))
    return [op for _, op in sorted(found)]


def requested_matrix_ops(text: str) -> tuple[MatrixOp, ...] | None:
    """Every result a one-matrix question asks for, in order; None for a composition.

    ``find the determinant and inverse of [[2,1],[5,3]]`` → ``("determinant", "inverse")``;
    ``the inverse of [[…]] without computing the determinant`` → ``("inverse",)``: an
    operation named as the method is no result. ``the inverse of the transpose of [[…]]``
    and ``the inverse of [[…]] and the determinant of the inverse`` ask for a result of
    two operations, so they are None, as is one matrix in a sum or a product ("… times
    2"): an operation answered about A alone would answer another question. A question
    about two matrices, or naming none, is ``()``.
    """
    lower = " ".join(text.lower().split())
    if lower.count("[[") != 1:
        return ()
    if (
        _COMPOSED.search(lower)
        or _IN_ARITHMETIC.search(lower)
        or any(word_index(lower, word) != -1 for word in _BINARY_WORDS)
    ):
        # "the determinant and rank of [[…]] times 2" asks about 2A, not A.
        return None
    return tuple(_asked(lower))


def without_matrix_cues(text: str) -> str:
    """The question with its operation words and its matrix taken out.

    What is left is glue ("find the … and … of") or another request ("and tell me a
    joke"), which the direct-reply guard reads.
    """
    lower = text.lower()
    start, end = lower.find("[["), lower.find("]]")
    kept = text[:start] + " " + text[end + 2 :] if 0 <= start < end else text
    for _, cues in _CUES:
        for cue in sorted(cues, key=len, reverse=True):
            while (at := _first_at(kept.lower(), cue)) != -1:
                stop = at + len(cue)
                while stop < len(kept) and kept[stop].isalpha():
                    stop += 1  # "eigenvalues", "diagonalize", "inverses"
                kept = kept[:at] + " " + kept[stop:]
    return " ".join(kept.split())
