"""Fact selectors must support every stored section without weakening deletion identity."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.routers.memories import router


@pytest.mark.parametrize("length", [2001, 4018, 4019])
def test_delete_fact_preserves_valid_long_selector_and_rejects_oversize(length):
    app = FastAPI()
    app.include_router(router)
    owner_id, memory_id = uuid4(), uuid4()
    session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=owner_id)
    app.dependency_overrides[get_settings_dep] = lambda: Settings()
    selector = "As of 2026-09-04: " + "📝" * (length - 18)
    with patch("app.services.memory.delete_memory_fact", AsyncMock(return_value=True)) as delete:
        response = TestClient(app).delete(
            f"/memories/{memory_id}/facts/0", params={"fact_text": selector}
        )

    assert response.status_code == (422 if length > 4018 else 204)
    if length > 4018:
        delete.assert_not_awaited()
    else:
        delete.assert_awaited_once()
        assert delete.await_args.args[2:] == (owner_id, memory_id, 0)
        assert delete.await_args.kwargs == {"expected_text": selector}
