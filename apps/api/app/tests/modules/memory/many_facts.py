"""Facts for timing the pairwise memory checks (CX-3, CX-5)."""

from types import SimpleNamespace
from uuid import uuid4


def many_facts(count: int) -> list[SimpleNamespace]:
    """``count`` active facts of one type, no two alike: every pair is compared."""
    return [
        SimpleNamespace(
            id=uuid4(),
            type="fact",
            status="active",
            text="Enjoys " + " ".join(f"w{index}x{step}" for step in range(8)),
            last_confirmed_at=None,
            updated_at=index,
        )
        for index in range(count)
    ]
