"""Validate the normalized query at the HTTP boundary."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.core.deps import get_current_user
from app.main import create_app


@pytest.mark.parametrize("query", ["  ", "\t\n", " a ", "x" * 201])
def test_search_rejects_invalid_normalized_query(query):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=uuid4())
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    with patch(
        "app.services.search.search_conversations", AsyncMock(return_value=([], 0))
    ) as search:
        response = TestClient(app).get("/search", params={"q": query})

    assert response.status_code == 422
    search.assert_not_awaited()


@pytest.mark.parametrize("query", ["  hello\t", " " * 201 + "ok" + " " * 201])
def test_search_passes_normalized_query(query):
    app = create_app()
    user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id=user_id)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    with patch(
        "app.services.search.search_conversations", AsyncMock(return_value=([], 0))
    ) as search:
        response = TestClient(app).get("/search", params={"q": query})

    assert response.status_code == 200
    assert search.await_args.args[1] == user_id
    assert search.await_args.kwargs["query"] == query.strip()
