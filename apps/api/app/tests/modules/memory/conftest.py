from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _no_memory_areas(request: pytest.FixtureRequest):
    """Unit tests drive the workflow with mock sessions; real-DB tests keep the query."""
    if "db_session" in request.fixturenames:
        yield
        return
    with patch("app.modules.memory.repository.list_areas", AsyncMock(return_value=[])):
        yield


@pytest.fixture
def quoting_model():
    """A mocked op written without a quote stands for a model that quoted the user line
    stating it, as their own life: these tests are about what a pass does with a fact the
    user did state (``test_grounding`` holds the quote checks themselves)."""
    from app.modules.memory import extraction_workflow
    from app.modules.memory.grounding import grounded_source

    compose = extraction_workflow.compose_writes

    def quoted(snapshot, lines, asks, ops, **kwargs):
        sources = kwargs.get("sources") or ()

        def line_for(op):
            for line in sources:
                if grounded_source(
                    quote=line.text,
                    fact=op.text,
                    stated_as="own_life",
                    lines=sources,
                    explicit_remember=False,
                ):
                    return line.text
            return sources[-1].text if sources else None

        ops = [
            op
            if op.quote or op.op in {"delete", "mute"}
            else op.model_copy(update={"quote": line_for(op), "stated_as": "own_life"})
            for op in ops
        ]
        return compose(snapshot, lines, asks, ops, **kwargs)

    with patch.object(extraction_workflow, "compose_writes", quoted):
        yield
