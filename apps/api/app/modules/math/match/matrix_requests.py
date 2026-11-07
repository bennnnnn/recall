"""Which results one matrix question asks for: "the determinant and inverse of [[2,1],[5,3]]".

``matrix_signal`` names one operation. A question that lists several (determinant and
inverse, rank and transpose, eigenvalues and eigenvectors) wants every one of them, and a
question that applies one to another's result ("the inverse of the transpose of …") wants
neither of them on its own: that is a composition, and the reader declines it.
"""

from __future__ import annotations

from itertools import pairwise

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


def _first_at(lower: str, cue: str) -> int:
    """Where ``cue`` first starts a word (``det`` also as ``det(``), or -1."""
    if cue in _WHOLE:
        return word_index(lower, cue)
    start = 0
    while (at := lower.find(cue, start)) != -1:
        if at == 0 or not lower[at - 1].isalpha():
            return at
        start = at + 1
    return -1


def _named(lower: str) -> list[tuple[int, int, MatrixOp]]:
    """``(start, end, op)`` for each operation named, in the order the question names them."""
    found: list[tuple[int, int, MatrixOp]] = []
    for op, cues in _CUES:
        spots = [(at, at + len(cue)) for cue in cues if (at := _first_at(lower, cue)) != -1]
        if spots:
            start, end = min(spots)
            found.append((start, end, op))
    return sorted(found)


def requested_matrix_ops(text: str) -> tuple[MatrixOp, ...] | None:
    """Every result a one-matrix question lists, in order; None for a composition.

    ``find the determinant and inverse of [[2,1],[5,3]]`` → ``("determinant", "inverse")``.
    ``the inverse of the transpose of [[…]]`` asks for one result of two operations, so
    it is None: answering either operation alone would answer another question. A
    question about two matrices, or naming fewer than two operations, is ``()``.
    """
    lower = text.lower()
    if lower.count("[[") != 1 or any(word_index(lower, word) != -1 for word in _BINARY_WORDS):
        return ()
    named = _named(lower)
    if len(named) < 2:
        return ()
    for (_, end, _op), (start, _, _next) in pairwise(named):
        gap = lower[end:start]
        # "the determinant of the inverse": the next operation's argument is this one's.
        if "[[" not in gap and word_index(gap, "of") != -1:
            return None
    return tuple(op for _, _, op in named)


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
