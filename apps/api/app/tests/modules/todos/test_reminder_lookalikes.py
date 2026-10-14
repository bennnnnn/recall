"""Ordinary turns that only sound like reminders keep the model's reply.

Found by the behavior sweep (``app/tests/behavior/sweep.py``): "Can you add
3 + 4 using the same method?" was answered "When should I remind you?".
"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules import home as home_service
from app.modules import todos as todos_service
from app.modules.todos import repository as todos_repo
from app.modules.todos.spoken_add import (
    adds_to_prior_reply,
    claims_a_reminder_change,
    mentions_reminders,
    parse_spoken_add,
    reply_when_nothing_saved,
)
from app.modules.todos.spoken_change import asks_to_read_reminders

REACT_TODO_REPLY = (
    "Create a new array instead of mutating the old one:\n\n"
    "```tsx\ntype Todo = { id: number; text: string; done: false };\n"
    "const [todos, setTodos] = useState<Todo[]>([]);\n```\n\n"
    "The key part is `setTodos((prev) => [...prev, newItem])`."
)
TRIP_PLAN = (
    "Day 1 (Fri): Addis → Debre Markos, overnight there. "
    "Day 2 (Sat): Debre Markos → Gondar via Bahir Dar. Day 3: Gondar's castles."
)
TRIP_REPLY = (
    "Here's the updated road trip:\n\n- **Fri:** Addis → Debre Markos\n"
    "- **Sat, 9:00 AM:** Arrive in **Bahir Dar**, boat out to the Lake Tana monasteries\n"
    "- **Sun:** Gondar's castles"
)
SEEDED = ("call mom", "dentist appointment", "gym", "pay rent")


def _saved(title: str) -> MagicMock:
    item = MagicMock()
    item.id = uuid4()
    item.content = title
    item.topic = "Reminders"
    item.checked = False
    item.due_at = None
    item.recurrence_rule = None
    item.source = "chat"
    return item


async def _finalize(
    user_text: str, reply: str, *, prior: str | None = None
) -> tuple[str, int, AsyncMock, AsyncMock]:
    items = [_saved(title) for title in SEEDED]
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(todos_repo, "list_for_user", AsyncMock(return_value=items))
        )
        create = stack.enter_context(
            patch.object(
                todos_repo,
                "create",
                AsyncMock(side_effect=lambda _session, **fields: SimpleNamespace(**fields)),
            )
        )
        update = stack.enter_context(patch.object(todos_repo, "update", AsyncMock()))
        stack.enter_context(
            patch.object(todos_repo, "get_open_dated_duplicate", AsyncMock(return_value=None))
        )
        stack.enter_context(patch.object(home_service, "invalidate_home_cache", AsyncMock()))
        text, applied = await todos_service.materialize_reminder_fences(
            AsyncMock(),
            user_id=uuid4(),
            chat_id=uuid4(),
            assistant_text=reply,
            user_timezone="Africa/Nairobi",
            user_text=user_text,
            prior_assistant=prior,
        )
    return text, applied, create, update


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_text", "reply", "prior"),
    [
        (
            "Can you add 3 + 4 using the same method?",
            "Same method: start at 3 and count up 4 more.\n\n**3 + 4 = 7**",
            "Start at 3 and count up 3 more. **3 + 3 = 6**",
        ),
        ("how do I add a todo item to a list in React state?", REACT_TODO_REPLY, None),
        (
            "Make a grocery list for tacos",
            "Here's a grocery list for **taco night**:\n\n- Tortillas\n- Ground beef\n- Limes",
            None,
        ),
        (
            "change of plans: it's pouring, so no grill. what should I cook?",
            "Try smash burgers in a skillet.\n\n**Quick grocery list**\n- 1 onion\n- Buns",
            "For four, figure about 1.5 lb of ground beef.",
        ),
        (
            "remind me how to convert Celsius to Fahrenheit",
            "Quick reminder — it's °F = °C × 9/5 + 32.",
            None,
        ),
        ("finish the story", "…and the lantern never went out again. **The End.**", None),
        ("delete a git branch", "Run `git branch -d my-branch`.", None),
        ("Add a stop in Bahir Dar on Saturday at 9am", TRIP_REPLY, TRIP_PLAN),
        ("mark it done", "Here's the essay with the edits marked.", "A draft essay about rain."),
    ],
)
async def test_lookalike_turn_keeps_the_reply(user_text, reply, prior):
    text, applied, create, update = await _finalize(user_text, reply, prior=prior)
    assert (text, applied) == (reply, 0)
    create.assert_not_awaited()
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_that_after_a_draft_edits_the_draft():
    draft = "```email\nSubject: Running late\n\nHi team, …\n```"
    reply = "```email\nSubject: Running late\n\nHi team, I'll be late tomorrow at 9am.\n```"
    text, applied, create, _ = await _finalize(
        "add that I'll be late tomorrow at 9am", reply, prior=draft
    )
    assert (text, applied) == (reply, 0)
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_change_claim_for_a_missing_reminder_is_not_passed_on():
    text, applied, _, update = await _finalize("uncheck buy milk", "Reopened: buy milk.")
    assert applied == 0
    assert text.startswith("Could not")
    update.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_real_add_after_an_unrelated_reply_still_saves():
    text, applied, create, _ = await _finalize(
        "add call the bank tomorrow at 9am",
        "Set: call the bank — tomorrow, 9:00 AM.",
        prior="Here's a pasta recipe: boil the water, add salt.",
    )
    assert applied == 1
    create.assert_awaited_once()
    assert "call the bank" in text.lower()


def test_code_is_not_reminder_talk():
    assert not mentions_reminders(REACT_TODO_REPLY)
    assert not mentions_reminders("```python\ntodos = []\nreminders = {}\n```")
    assert mentions_reminders("Your reminders: call mom at 6.")


@pytest.mark.parametrize(
    ("text", "about"),
    [
        ("Quick reminder — it's 9/5 + 32.", False),
        ("Here's a grocery list for taco night.", False),
        ("I'll add milk to your grocery list.", True),
        ("Set: read — Monday, Oct 12, 8:00 AM.", True),
    ],
)
def test_mentions_reminders(text, about):
    assert mentions_reminders(text) is about


def test_change_claims_outside_code_only():
    assert claims_a_reminder_change("Reopened: buy milk.")
    assert not claims_a_reminder_change("```ts\nconst t = { done: false };\n```")
    assert not claims_a_reminder_change(None)


def test_code_field_lines_are_not_stripped_as_claims():
    reply = "```yaml\ndone: false\nset: 3\n```\n\nYour reminders are unchanged."
    assert reply_when_nothing_saved(reply, "how do I mark a task done in yaml?") == reply


@pytest.mark.parametrize(
    "user_text",
    [
        "remind me how to convert Celsius to Fahrenheit",
        "remind me what pv=nrt means",
        "remind me why the sky is blue",
        "add that I'll be late",
    ],
)
def test_questions_are_not_spoken_adds(user_text):
    assert parse_spoken_add(user_text) is None


@pytest.mark.parametrize(
    ("user_text", "reads"),
    [
        ("What's scheduled at the Hollywood Bowl this weekend?", False),
        ("what's scheduled in Paris", False),
        ("whats scheduled for tomorrow", True),
        ("what is scheduled at 3pm", True),
        ("what is scheduled in the morning", True),
        ("what reminders do I have", True),
    ],
)
def test_asks_to_read_reminders(user_text, reads):
    assert asks_to_read_reminders(user_text) is reads


def test_adds_to_prior_reply_needs_overlap_and_no_reminder_talk():
    assert adds_to_prior_reply("a stop in Bahir Dar", prior_assistant=TRIP_PLAN, reply=TRIP_REPLY)
    assert not adds_to_prior_reply("call mom", prior_assistant=TRIP_PLAN, reply=TRIP_REPLY)
    assert not adds_to_prior_reply(
        "a stop in Bahir Dar", prior_assistant=TRIP_PLAN, reply="Set: a stop — Saturday, 9:00 AM."
    )
    assert not adds_to_prior_reply(
        "a stop in Bahir Dar", prior_assistant="Your reminders: Bahir Dar trip.", reply=TRIP_REPLY
    )
