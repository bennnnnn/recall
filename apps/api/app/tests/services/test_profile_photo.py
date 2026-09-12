from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Attachment, User
from app.models.schemas import UserOut
from app.services import account_lifecycle, auth


def _user() -> User:
    return User(
        id=uuid4(),
        email="profile@example.com",
        name="Before",
        avatar_url="https://example.com/provider.jpg",
        memory_enabled=True,
    )


def _photo(user: User, **overrides) -> Attachment:
    fields = {
        "id": uuid4(),
        "user_id": user.id,
        "content_type": "image/jpeg",
        "size_bytes": 1024,
        "source": "upload",
        "verified_at": datetime.now(UTC),
        "message_id": None,
        "library_visible": True,
    }
    return Attachment(**(fields | overrides))


@pytest.mark.parametrize(
    "override",
    [
        {"verified_at": None},
        {"content_type": "text/plain"},
        {"source": "search"},
        {"message_id": uuid4()},
        {"size_bytes": 0},
        {"size_bytes": 10 * 1024 * 1024 + 1},
        None,
    ],
)
async def test_profile_rejects_unusable_photo_without_saving_name(override):
    user = _user()
    photo = _photo(user, **override) if override is not None else None
    attachment_id = photo.id if photo else uuid4()
    session = AsyncMock()
    with (
        patch.object(
            account_lifecycle.attachments_repo, "get_by_id", AsyncMock(return_value=photo)
        ) as get_photo,
        patch.object(account_lifecycle.users_repo, "update", AsyncMock()) as update,
        patch.object(account_lifecycle.home_service, "invalidate_home_cache", AsyncMock()) as cache,
    ):
        with pytest.raises(ValueError, match="uploaded photo"):
            await account_lifecycle.update_account(
                session,
                user,
                Settings(_env_file=None),
                {"name": "After", "avatar_url": f"/attachments/{attachment_id}/file"},
            )
    get_photo.assert_awaited_once_with(session, attachment_id, user.id, for_update=True)
    update.assert_not_awaited()
    cache.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    assert user.name == "Before"


async def test_profile_save_rolls_back_without_cache_invalidation_on_commit_failure():
    user = _user()
    photo = _photo(user)
    session = AsyncMock()
    session.commit.side_effect = RuntimeError("commit failed")
    with (
        patch.object(
            account_lifecycle.attachments_repo, "get_by_id", AsyncMock(return_value=photo)
        ),
        patch.object(account_lifecycle.home_service, "invalidate_home_cache", AsyncMock()) as cache,
    ):
        with pytest.raises(RuntimeError, match="commit failed"):
            await account_lifecycle.update_account(
                session,
                user,
                Settings(_env_file=None),
                {"name": "After", "avatar_url": f"/attachments/{photo.id}/file"},
            )
    session.rollback.assert_awaited_once()
    cache.assert_not_awaited()


@pytest.mark.parametrize("custom", [True, False])
async def test_google_login_preserves_uploaded_photo_and_refreshes_provider_photo(custom):
    user = _user()
    if custom:
        user.avatar_url = f"/attachments/{uuid4()}/file"
    avatar_before = user.avatar_url
    payload = {
        "sub": "google-profile-test",
        "email": user.email,
        "picture": "https://example.com/new-provider.jpg",
    }
    output = UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        default_model="free-chat",
        response_style="balanced",
        memory_enabled=True,
        created_at=datetime.now(UTC),
    )
    with (
        patch.object(auth, "verify_google_id_token", AsyncMock(return_value=payload)),
        patch.object(auth.users_repo, "get_by_google_sub", AsyncMock(return_value=user)),
        patch.object(auth.users_repo, "update", AsyncMock(return_value=user)) as update,
        patch.object(auth.tokens_service, "issue_token_pair", AsyncMock(return_value=("a", "r"))),
        patch.object(auth.UserOut, "model_validate", return_value=output),
    ):
        await auth.login_with_google(AsyncMock(), Settings(_env_file=None), "id", AsyncMock())
    assert update.await_args.kwargs["avatar_url"] == (
        avatar_before if custom else payload["picture"]
    )


@pytest.mark.parametrize("provider", ["google", "apple"])
@pytest.mark.parametrize("saved_name", ["Edited name", "", "   ", None])
async def test_provider_login_only_fills_a_blank_saved_name(provider, saved_name):
    user = _user()
    user.name = saved_name
    payload = {
        "sub": "profile-login",
        "email": user.email,
        "name": "Provider name",
        "email_verified": True,
    }
    output = UserOut(
        id=user.id,
        email=user.email,
        name=saved_name,
        avatar_url=user.avatar_url,
        default_model="free-chat",
        response_style="balanced",
        memory_enabled=True,
        created_at=datetime.now(UTC),
    )
    with (
        patch.object(auth, f"verify_{provider}_id_token", AsyncMock(return_value=payload)),
        patch.object(auth.users_repo, f"get_by_{provider}_sub", AsyncMock(return_value=user)),
        patch.object(auth.users_repo, "update", AsyncMock(return_value=user)) as update,
        patch.object(auth.tokens_service, "issue_token_pair", AsyncMock(return_value=("a", "r"))),
        patch.object(auth.UserOut, "model_validate", return_value=output),
    ):
        if provider == "google":
            await auth.login_with_google(AsyncMock(), Settings(_env_file=None), "id", AsyncMock())
        else:
            await auth.login_with_apple(
                AsyncMock(), Settings(_env_file=None), "id", AsyncMock(), name="Provider name"
            )
    expected = saved_name if saved_name and saved_name.strip() else "Provider name"
    assert update.await_args.kwargs.get("name", saved_name) == expected
