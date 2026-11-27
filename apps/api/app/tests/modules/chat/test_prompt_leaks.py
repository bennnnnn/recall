"""A sentence that tells the user about the prompt's own parts comes off a reply."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.chat.finalize_contracts import STOPPED_REPLY_PASSES
from app.modules.chat.finalize_passes import FINALIZE_PASSES
from app.modules.chat.prompt_leaks import drop_prompt_leaks, drop_prompt_leaks_pass

ANSWER = "For a first investment, a low-cost index fund is a sound start."
# The live reply (2026-10-25), on an investing question.
LIVE_LEAK = (
    "The memory block contains details that don't match this conversation. It names a "
    "different person and preferences that conflict with what you've told me, so I'm "
    "setting it aside and answering from what you've shared, Dev."
)


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (f"{LIVE_LEAK}\n\n{ANSWER}", ANSWER),
        (f"{LIVE_LEAK} {ANSWER}", ANSWER),
        (
            f"Sure thing, Dev! Your saved memory block lists a nursing exam. {ANSWER}",
            f"Sure thing, Dev! {ANSWER}",
        ),
        (f"My system prompt says your name on file is Dev. {ANSWER}", ANSWER),
        (f"Per the [Chemistry note], no IUPAC name came back. {ANSWER}", ANSWER),
        (f"[BEGIN UNTRUSTED CONTENT — saved memory] was empty.\n\n{ANSWER}", ANSWER),
        (
            f"Hi Dev!\n\n- The profile block in this chat says Chicago.\n- {ANSWER}",
            f"Hi Dev!\n\n- {ANSWER}",
        ),
        # The sentence that points back at the leak goes with it; the next one stays.
        (
            f"The memory block names a different person. That is set aside. {ANSWER}",
            f"That is set aside. {ANSWER}",
        ),
        (
            f"The memory block names a different person. It conflicts with what you've told "
            f"me. {ANSWER}",
            ANSWER,
        ),
    ],
)
def test_a_sentence_about_the_prompt_comes_off(reply: str, expected: str) -> None:
    assert drop_prompt_leaks(reply, "how should I start investing?") == expected


@pytest.mark.parametrize(
    "reply",
    [
        # Everyday meanings of the same words.
        "When you call `free()`, the memory block goes back to the heap.",
        "malloc returns a pointer to a memory block of at least the requested size.",
        "A system prompt sets the model's role before the first user message.",
        "Your profile block in the CMS template holds the avatar and bio.",
        # Words about the user without a prompt part.
        "Earlier I called you Sam; sorry, Dev. Here is the plan for this conversation.",
        f"From what you've told me, a low-risk start fits. {ANSWER}",
        # Inside code, a table or a heading nothing changes.
        "```python\n# the memory block on file for this conversation\nx = 1\n```",
        "Use `system prompt on file` as the key.",
        "| term | meaning |\n| --- | --- |\n| memory block about you | a note |",
        "## The memory block in this conversation",
        ANSWER,
        # Second-person words an answer about a CMS or an LLM uses (review, 2026-10-25).
        "Keep your name and tone rules in the system message so the model knows about you.",
        "Add a profile block to the sidebar so it shows your name and avatar.",
        "The profile block displays information about you to visitors.",
        # "On file" that is not this user's record.
        "When you free it, the allocator marks this memory block as free; on file systems "
        "it differs.",
        "Each memory block on file is tracked by the bitmap. It is efficient.",
        # A quote is the quoted text.
        '> "The system prompt is set aside in this chat," she said.\n\nFrom the novel.',
        "> The system prompt in this conversation is fixed.",
        # Sentences that only point back after a leak go; here there is none.
        "Your memory block is misaligned. This is what you've told me about the board.",
    ],
)
def test_other_replies_are_left_alone(reply: str) -> None:
    assert drop_prompt_leaks(reply, "why does free crash?") == reply


def test_a_chat_about_language_models_keeps_its_reply() -> None:
    reply = "The system message in this conversation sets the tone. It works best short."
    asks = ["how do I write instructions for an LLM agent?", "and for ChatGPT?"]
    for asked in asks:
        assert drop_prompt_leaks(reply, asked) == reply
    # An earlier message in the chat says what it is about.
    assert drop_prompt_leaks(reply, "and the tone?", "how do system prompts work?") == reply


@pytest.mark.parametrize(
    "earlier",
    [
        "I asked ChatGPT earlier but it was wrong",
        "I'm a GPT user",
        "give me a writing prompt for my class",
        "my boss wants a prompt reply",
    ],
)
def test_a_passing_mention_of_chatgpt_or_a_prompt_keeps_the_guard(earlier: str) -> None:
    reply = f"{LIVE_LEAK}\n\n{ANSWER}"
    assert drop_prompt_leaks(reply, "how should I invest 10k?", earlier) == ANSWER


@pytest.mark.parametrize(
    "query",
    [
        "What does your system prompt say about me?",
        "write a system prompt for my support bot",
        "what's in the memory block?",
    ],
)
def test_a_turn_that_asks_about_prompts_keeps_its_reply(query: str) -> None:
    reply = f"My system prompt says your name on file is Dev. {ANSWER}"
    assert drop_prompt_leaks(reply, query) == reply


def test_a_reply_that_is_only_a_leak_is_kept() -> None:
    assert drop_prompt_leaks(LIVE_LEAK, "hi") == LIVE_LEAK


def _state(
    text: str, *, server_text: bool = False, earlier: tuple[str, ...] = ()
) -> SimpleNamespace:
    ctx = SimpleNamespace(
        user_message_content="how do I start investing?",
        prompt_messages=[{"role": "system", "content": "about prompts"}]
        + [{"role": "user", "content": line} for line in earlier],
    )
    return SimpleNamespace(text=text, ctx=ctx, server_text=server_text)


def test_the_pass_cleans_a_model_reply_and_never_server_text() -> None:
    reply = f"{LIVE_LEAK}\n\n{ANSWER}"
    assert drop_prompt_leaks_pass(_state(reply)) == ANSWER  # type: ignore[arg-type]
    assert drop_prompt_leaks_pass(_state(reply, server_text=True)) == reply  # type: ignore[arg-type]


def test_the_pass_reads_the_users_recent_messages() -> None:
    reply = f"{LIVE_LEAK}\n\n{ANSWER}"
    on_prompts = _state(reply, earlier=("write me a system prompt",))
    assert drop_prompt_leaks_pass(on_prompts) == reply  # type: ignore[arg-type]


def test_the_pass_runs_on_every_reply_and_a_stopped_one() -> None:
    names = [finalize_pass.name for finalize_pass in FINALIZE_PASSES]
    assert names.index("prompt_leaks") == names.index("meta_notes") + 1
    assert "prompt_leaks" in STOPPED_REPLY_PASSES


# An instruction copied from the prompt opened a Class 8 speed answer (2026-10-30).
_PHYSICS_RULES = (
    "Physics answers:\n  - This is a physics problem. Do not describe the work as math, "
    "algebra, or solving equations.\n  - When verified results appear in a [BEGIN VERIFIED "
    "PHYSICS] block, use those exact numbers and units. Do not recompute. If no verified "
    "block is present, do not claim verification.\n"
    "Saved facts: Bini is building a recipe app called Spoon. Use metric units always."
)
_ECHO = (
    "This is a physics question. Do not describe the work as math, algebra, or solving "
    "equations. When verified results appear in a  block, use those exact numbers and units. "
    "Do not recompute. If no verified block is present, do not claim verification.\n\n"
    "No verified block is present, so I compute and check the result myself.\n\n"
    "**Given**\n$d = 29\\ \\text{km}$"
)


def test_instructions_copied_from_the_prompt_come_off() -> None:
    out = drop_prompt_leaks(_ECHO, "How far is the city?", instructions=_PHYSICS_RULES)
    assert out == "**Given**\n$d = 29\\ \\text{km}$"


@pytest.mark.parametrize(
    "reply",
    [
        # Ordinary advice in an instruction's shape, and a saved fact said back.
        "Use the formula v = d / t to find the speed of the car here.",
        "Bini is building a recipe app called Spoon, so the tips below fit it.",
        "Do not mix the two solutions before the test tube cools down.",
    ],
)
def test_a_sentence_the_prompt_does_not_hold_stays(reply: str) -> None:
    assert drop_prompt_leaks(reply, "q", instructions=_PHYSICS_RULES) == reply


def test_the_pass_reads_only_the_fixed_rules() -> None:
    # The physics rules a model copied are caught by the pass's own rule text; a reply
    # quoting the user's recipe, to-do or a bitcoin explainer is not (review, 2026-10-30).
    from app.modules.chat.prompt_leaks import _rule_grams

    rules = _rule_grams()
    assert drop_prompt_leaks(_ECHO, "q", rules=rules) == "**Given**\n$d = 29\\ \\text{km}$"
    for reply in (
        "1. Use a heavy-based pan for the risotto.\n2. When the stock is simmering, add one "
        "ladle at a time.\n3. Never let the rice dry out.",
        "You have two things on your list. Put the bins out on Thursday night. Call the dentist.",
        "Each verified block is then added to the chain, and it links to the one before it.",
    ):
        assert drop_prompt_leaks(reply, "q", rules=rules) == reply


@pytest.mark.parametrize(
    "reply",
    [
        "How to write a recipe card:\n- Give numbered steps, one action each, in the order "
        "they are done.\n- Keep it short.",
        "Never open with a rhetorical hook. It wastes the reader's first seconds.",
    ],
)
def test_one_sentence_of_advice_like_a_rule_stays(reply: str) -> None:
    from app.modules.chat.prompt_leaks import _rule_grams

    assert drop_prompt_leaks(reply, "How do I write it?", rules=_rule_grams()) == reply


_EQUILIBRIUM = (
    "This is a school-style physics problem, so I'll walk through the reasoning without "
    "emoji.\n\nThe figure shows a point P in static equilibrium, held by three forces."
)


def test_a_reply_announcing_its_emoji_rule_loses_that_sentence() -> None:
    # Live, 2026-11-03: a scanned equilibrium problem opened by reciting the style rule.
    out = drop_prompt_leaks(_EQUILIBRIUM, "Find the force F of the cord")
    assert out == "The figure shows a point P in static equilibrium, held by three forces."


@pytest.mark.parametrize(
    "reply",
    [
        # Tutoring narration about the method is the answer's own.
        "This is a projectile problem, so I'll split it into horizontal and vertical parts.",
        # Emoji as the subject, not the reply's style.
        "The 🙂 emoji means a polite smile in most chats.",
    ],
)
def test_narration_about_the_method_or_emoji_as_a_topic_stays(reply: str) -> None:
    assert drop_prompt_leaks(reply, "help me with this") == reply


def test_a_chat_about_emoji_keeps_a_reply_that_names_them() -> None:
    reply = "I'll keep the emoji in, since you asked for a fun caption. 🎉 Beach day!"
    assert drop_prompt_leaks(reply, "write a caption with emoji") == reply


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        (
            "This is a current-events question, so I'll check the latest reporting before "
            "answering.\n\nThey have since reconciled.",
            "They have since reconciled.",
        ),
        (
            "This is a projectile problem, so I'll split it into two parts. Horizontally, "
            "the speed stays 12 m/s.",
            "Horizontally, the speed stays 12 m/s.",
        ),
        (
            "That's a great question, and I'll keep it short: yes.",
            "That's a great question, and I'll keep it short: yes.",
        ),
        (
            "It sounds like a tricky one, so let me lay it out. First, the area is 12.",
            "First, the area is 12.",
        ),
    ],
)
def test_an_opening_that_labels_the_message_and_announces_a_plan_comes_off(
    reply: str, kept: str
) -> None:
    assert drop_prompt_leaks(reply, "help") == kept


@pytest.mark.parametrize(
    "reply",
    [
        # Only the opening, and only a label with a plan.
        "Horizontally, the speed stays 12 m/s. This is a projectile problem, so I'll add a sketch.",
        "This is a classic problem.\n\nThe answer is 12.",
        # A reply that is only the label keeps it rather than saying nothing.
        "This is a hard question, so I'll need a moment.",
        "```python\nthis is a test, so i'll print it.\n```",
    ],
)
def test_other_openings_stay(reply: str) -> None:
    assert drop_prompt_leaks(reply, "help") == reply


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        # A decimal point is no sentence end.
        (
            "This is a rate problem, so I'll start with v = 3.5 m/s. Then t = d/v.",
            "Then t = d/v.",
        ),
    ],
)
def test_the_label_ends_at_its_sentence_not_a_decimal(reply: str, kept: str) -> None:
    assert drop_prompt_leaks(reply, "help") == kept


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        # A colon starts the answer: the sentence stays.
        ("That's a great question, and I'll keep it short: yes. The area is 12.", "help"),
        # An emoji named as the topic, not the reply's style.
        (
            "I'm fairly sure that is the Face with Tears of Joy emoji.",
            "what's the crying laughing face called?",
        ),
        # A stop inside the sentence ("e.g.", "Fig.") is no sentence end: kept whole.
        (
            "This is a physics problem, so I'll use a free-body diagram, e.g. one per mass. T1 = 5 N.",
            "help",
        ),
        ("This is a rate problem, so I'll use Fig. 2 and v = d/t.", "help"),
        # Asked about the prompt: nothing is cut.
        (
            "I can't share my system prompt. I'll use emoji sparingly.",
            "what's in your system prompt?",
        ),
    ],
)
def test_answers_and_topics_stay(reply: str, asked: str) -> None:
    assert drop_prompt_leaks(reply, asked) == reply


def test_an_opening_that_narrates_the_users_message_comes_off() -> None:
    """Live 2026-11-06: the planning paragraph reached the user above the answer."""
    reply = (
        'The user says "ok and like 5 common beginner mistakes i should avoid?" This is a '
        "factual list request, so I'll give five clear mistakes with short explanations. "
        "Numbered list, bold labels.\n\n1. **Mixing up `=` and `==`** - one assigns."
    )
    assert drop_prompt_leaks(reply, "ok and like 5 common beginner mistakes") == (
        "1. **Mixing up `=` and `==`** - one assigns."
    )


_BAHIR_DAR_PLAN = (
    "The user asks what Bahir Dar has, a follow-up to the size question, so I give new "
    "points, not a recap. The user prefers brief replies, so I keep it short."
)
_BAHIR_DAR_ANSWER = "Bahir Dar has **Lake Tana**, its island monasteries and the Blue Nile Falls."


@pytest.mark.parametrize(
    "reply",
    [
        # Live 2026-11-27 (free-chat): the plan in the present tense, its own paragraph...
        f"{_BAHIR_DAR_PLAN}\n\n{_BAHIR_DAR_ANSWER}",
        # ...or leading the answer's paragraph.
        f"{_BAHIR_DAR_PLAN} {_BAHIR_DAR_ANSWER}",
        # A student's profile, the same shape.
        f"The user is a student, so I keep the answer simple.\n\n{_BAHIR_DAR_ANSWER}",
        # Live 2026-11-27 (Pro, free-chat, this branch's first run): the typo read aloud.
        'The user means "Bahir Dar," and they\'re asking what the city has, meaning its main '
        "attractions and features. This is settled knowledge, so I'll answer from what I know."
        f"\n\n{_BAHIR_DAR_ANSWER}",
    ],
)
def test_a_plan_in_the_present_tense_comes_off(reply: str) -> None:
    assert drop_prompt_leaks(reply, "What does vahir dar has") == _BAHIR_DAR_ANSWER


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        # Live 2026-11-27 (Pro, free-chat): the prompt's "your last reply", said to the user.
        (
            'Your last reply gave six energy types, so "the second one" is wind. Wind power '
            "turns moving air into electricity.",
            "Wind power turns moving air into electricity.",
        ),
        (
            "Your last reply covered budget picks, so the next useful step is judging specs."
            "\n\n## Specs to Check",
            "## Specs to Check",
        ),
        # Live 2026-11-27: "Memory says" in the second paragraph.
        (
            "Congratulations, Bini! 🎉\n\nMemory says you're a student, so is this part-time?",
            "Congratulations, Bini! 🎉\n\nYou're a student, so is this part-time?",
        ),
        # A plan said with "so here is".
        (
            "Bahir Dar has more beyond the lake, and the user prefers short replies, so here is "
            "a brief extension.\n\n## More About Bahir Dar",
            "## More About Bahir Dar",
        ),
    ],
)
def test_an_opening_on_the_earlier_reply_comes_off(reply: str, kept: str) -> None:
    assert drop_prompt_leaks(reply, "and the second one?") == kept


def test_the_users_own_reply_to_someone_stays() -> None:
    reply = "Your last reply to Sam sounded cold. Try this instead:\n\n```message\nHey Sam!\n```"
    assert drop_prompt_leaks(reply, "how do I reply to Sam") == reply


@pytest.mark.parametrize(
    "reply",
    [
        # A design or product answer about its end user, in the first person.
        "The user wants to sign in quickly, so I put the login button at the top.\n\n"
        "Then the form asks for the email only.",
        "The end user asks for a refund, so I route the ticket to billing.\n\nIt takes a day.",
        # A user story says "I" and "so I can" as the user.
        "**User story:** As a user, I want to reset my password so I can sign in again.\n\n"
        "**Acceptance:** the link expires after an hour.",
        # Spoken to the person, it stays.
        "You prefer brief replies, so here it is short: **Lake Tana**.",
    ],
)
def test_first_person_answers_about_a_user_stay(reply: str) -> None:
    assert drop_prompt_leaks(reply, "write a short user story for a login screen") == reply


@pytest.mark.parametrize(
    "reply",
    [
        # The whole reply, or an answer about users that names them.
        'The user says "hi".',
        "The user story is the unit of work in Scrum.\n\nIt names who wants what and why.",
        "The users asked for dark mode most often.\n\nSo it shipped first.",
        # An explanation that opens on a user plans nothing (review of #2306).
        "The user wants to log in, so the app redirects to /auth and checks the token.\n\n"
        "Then the session is stored.",
        "The user needs to reset a password: they get an email link.\n\nThe link expires.",
    ],
)
def test_other_replies_about_users_stay(reply: str) -> None:
    assert drop_prompt_leaks(reply, "tell me about user stories") == reply


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        # Live 2026-11-07, "Teach me American proverbs" after an English-words course.
        (
            "Memory says they've been learning useful English words, one concept at a time, "
            "and they're on a fresh subject now, so this is a new lesson. Since they asked for "
            "a whole subject, I'll teach Lesson 1 with the most useful first piece.\n\n"
            "Let's start with the proverbs you'll hear most.\n\n### Lesson 1: Proverbs",
            "Let's start with the proverbs you'll hear most.\n\n### Lesson 1: Proverbs",
        ),
        (
            "They want a lesson on proverbs, so I'll start with the ten most common.\n\n"
            "### Lesson 1: Proverbs",
            "### Lesson 1: Proverbs",
        ),
        (
            "The learner is on Lesson 3, so I'll continue with dictionaries.\n\n"
            "### Lesson 4: Dictionaries",
            "### Lesson 4: Dictionaries",
        ),
        (
            "Based on memory, they prefer short answers, so I'll keep it brief.\n\n"
            "**Paris** is the capital of France.",
            "**Paris** is the capital of France.",
        ),
        # What is remembered is said to the person, not credited to memory.
        (
            "Memory says you're vegetarian, so here are three dinners:\n\n1. **Dal**",
            "You're vegetarian, so here are three dinners:\n\n1. **Dal**",
        ),
        (
            "According to my memory, you live in Addis, so the closest is Bole.",
            "You live in Addis, so the closest is Bole.",
        ),
    ],
)
def test_a_reply_speaks_to_the_person_not_about_them(reply: str, kept: str) -> None:
    assert drop_prompt_leaks(reply, "teach me") == kept


@pytest.mark.parametrize(
    "reply",
    [
        # Spoken to the person: it stays.
        "You've been learning English words, so let's add proverbs.\n\n### Lesson 1: Proverbs",
        # About other people, or a plan about nobody in particular.
        "The Romans built roads to move armies, and I'll explain how.\n\nThey paved them.",
        "They say actions speak louder than words, so let me explain it.\n\nIt means deeds.",
        "Farmers want rain in spring, so I'll explain irrigation.\n\nWater is piped in.",
        # Memory a program keeps (review of #2326).
        "Variables are kept in memory, so I'll show how the stack works.\n\nThe stack grows down.",
        "The memory shows you the value of x at each step.\n\nSet a breakpoint first.",
        # A story or dialogue (review of #2326).
        "They asked me to stay, but I'll go.\n\nShe walked out into the rain.",
        '"They want the money by Friday, so I\'ll pay," he said.\n\nShe nodded.',
        # Narration with nothing after it: the reply is left as written.
        "They want a lesson on proverbs, so I'll start with the ten most common.",
    ],
)
def test_replies_that_speak_to_the_person_stay(reply: str) -> None:
    assert drop_prompt_leaks(reply, "teach me") == reply


def _drawing_state(text: str, line: str, *, contract: bool) -> SimpleNamespace:
    """A finalize state whose prompt carried the draw contract (``ctx.drawing``) or not."""
    ctx = SimpleNamespace(
        user_message_content=line,
        prompt_messages=[{"role": "user", "content": line}],
        drawing=object() if contract else None,
    )
    return SimpleNamespace(text=text, ctx=ctx, server_text=False)


@pytest.mark.parametrize(
    "lead",
    [
        "Here is the ```draw block representing this scenario:",
        "Here is the `draw` block representing this scenario:",
        "This draw block shows them.",
    ],
    ids=["fence-ticks", "one-tick", "pointing"],
)
def test_a_sentence_about_the_draw_block_comes_off(lead: str) -> None:
    """ "Here is the ```draw block representing this scenario" stood in a reply (textbook
    round, 2026-11-25): on a turn whose prompt asked for the block, it never reaches the
    phone, in any ticks."""
    reply = f"The force is largest at the start.\n\n{lead}\n\nThe area under the line is the work."
    state = _drawing_state(reply, "Draw a graph of force against distance.", contract=True)
    assert drop_prompt_leaks_pass(state) == (  # type: ignore[arg-type]
        "The force is largest at the start.\n\nThe area under the line is the work."
    )


@pytest.mark.parametrize(
    ("line", "contract"),
    [
        ("Why does my p5.js sketch leave trails?", False),
        ("My draw block flickers in Processing, why?", True),
        ("Why does my draw() loop leave trails?", True),
    ],
    ids=["no-contract", "user-says-draw-block", "user-says-draw-loop"],
)
def test_a_draw_block_of_the_user_s_own_stays(line: str, contract: bool) -> None:
    """p5.js and Processing have a draw block of their own (review of #2603, round 2)."""
    reply = (
        "Move `background(220)` into the draw block so the canvas clears every frame.\n\n"
        "1. Put setup code in setup().\n2. Move background() into the draw block."
    )
    state = _drawing_state(reply, line, contract=contract)
    assert drop_prompt_leaks_pass(state) == reply  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "reply",
    [
        "First, draw block diagrams for each subsystem.",
        "1. Draw blocks for each stage.\n2. Join them with arrows.",
        "Minecraft builders draw blocks on graph paper first.",
    ],
)
def test_draw_block_in_english_stays(reply: str) -> None:
    """ "Draw block diagrams" is English, never the prompt's block (review of #2603)."""
    assert drop_prompt_leaks(reply, "How do I design a control system?") == reply
