# Hand-off: make Recall talk like a person in a personal conversation (2026-11-20)

**For the next session.** Read this whole file first. Your job is in "What you must do".

**Branch:** `claude/natural-chat`. It's pushed, with no PR yet. Work on it, then open the PR.

## 1. What happened

The owner tested Recall with an 80-message chat called "Friend getting married". It covers a
girlfriend's wedding, then her mother, gifts and money, a marriage, children, and sex. Recall's
replies read like a cautious form letter, not a friend. The owner then had the 80 messages
replayed with fixes (in a Claude chat, with Claude Haiku standing in for Recall's models). Those
fixes were **never pushed** and are lost. Only their measured effect survives:

| pattern (80 replies) | Recall on main (before) | the lost fixes' replay (target) |
|---|---|---|
| ends on a question or offer | 65 | 14 |
| ends on an offer ("Would you like…", "Want me to…") | 36 | 4 |
| states a full date ("Friday, November 20, 2026") | 50 | 0 |
| numbered or bulleted list | 25 | 0 |
| 💛 emoji | 58 | 0 |
| any emoji | 69 | 15 |
| tells him to call 911 / an emergency number | 12 | 0 |
| brings up the bank or a lawyer | 37 | 16 |
| brings up the $500,000 | 40 | 19 |
| answers its own offer ("Yes, let's…") | 3 | 0 |
| refuses something not asked ("I can't help you…") | 3 | 0 |
| average reply length (characters) | 559 | 246 |

**The chat itself:** `apps/api/app/tests/behavior/replays/friend_getting_married.json`. For each
of the 80 turns it holds the user's message and Recall's reply on main ("before").

## 2. What was found: the prompt asked for most of it

Each pattern traces to a rule in the system prompt that asked for it. That was found by building
the real prompt for these turns through `app/tests/behavior/harness.py` (`route_case` with the
chat as `Case.history`) and reading it.

| pattern | the rule that caused it | where |
|---|---|---|
| ends on a question or offer | "Ending: at most one short plain line, **a question or an offer** of one concrete next step" | `app/modules/chat/prompt_constants/format.py`, `FORMAT_CONTRACT` |
| answers its own offer | "**A message after a question you asked is its answer**": news after "Would it help to plan what to ask your bank?" was read as yes | `prompt_constants/unclear.py`, `UNCLEAR_MESSAGE_HINT` |
| full dates | "When you name the weekday of a date, **write the full date with it**", which contradicts `NO_RECAP_NOTE`'s "a known day is just its weekday" | `app/services/time_context.py` (the clock block) |
| lists, bold, length | "Write it to be scanned on a phone … three or more parallel points are bullets", beside every message | `prompt_constants/format.py`, `READER_NOTE` (added by `message_notes.py`) |
| bank / $500,000 / the daughter in every reply | nothing limits repeating a concern | `prompt_constants/conversation.py`, `NO_RECAP_NOTE` |
| 💛 on 58 replies | the user's Emoji setting is "Lots": "a short friendly line may carry one", and nothing stops the same one every time. The finalize pass (`emoji_placement.py`) keeps emoji as written at "Lots" by design; at "A few" it already strips a 💛 between sentences | `app/modules/chat/response_tone.py`, `EMOJI_HINTS["more"]`, `emoji_note` |
| 911 twelve times | "When someone may be in danger … (**a story told as real**)" made a willing, if hard, situation an emergency; "Are you safe right now?" was asked again every turn | `prompt_constants/care.py`, `DISTRESS_RULE` |
| refusals and lectures | nothing about explicit detail, or about refusing what wasn't asked | `prompt_constants/care.py`, `PERSONAL_HELP_RULE` |

## 3. What is already done on the branch

These are prompt text only. No word list was added, and no reading or routing changed. Each rule
has a test in `app/tests/modules/chat/test_conversation_turn_rules.py` (plus updates in
`test_reply_shape_rules.py` and `test_time_context.py`).

1. **Ending:**
   - End on the last point.
   - A question only when the answer is needed to help.
   - An offer only of one concrete thing you can do now, never the same one again after the
     user lets it go.
   - No offer in a reply about the user's own life or feelings.
2. **Offers:** only a message that answers the question is its answer. News is never a yes, and
   the model never takes up its own offer.
3. **Dates:** a day the chat already named is "tomorrow", "today" or its weekday, never its full
   date again. A day new to the chat keeps weekday + full date, because the finalize pass
   `fix_clock` checks the weekday.
4. **Layout:** a message about the user's own life (news, a feeling, a choice they made) gets a
   few short plain lines, the way a friend texts back: no list, heading or bold.
5. **Repetition:** a concern, a warning or a piece of advice is said once, then not raised again
   unless something new changes it. A topic the user asks to drop is dropped, unless someone's
   safety depends on it.
6. **Emoji at "Lots":** each fits its line; never the same one reply after reply as a sign-off.
7. **Safety:**
   - Pressure, a hard situation or an unwise choice is not an emergency by itself: concern once,
     and "are you okay and do you feel safe?" asked once.
   - Telling them to leave or call 911 is only for a stated threat, violence, an injury, being
     kept from leaving, or saying they don't feel safe.
   - The suicide and self-harm rule is unchanged: it is never dropped, and the crisis line is
     given again.
8. **Personal help:**
   - A choice that is theirs gets an honest view once, then help with what they chose.
   - Explicit sexual detail is skipped in a few words ("I'll skip that part").
   - Nothing they didn't ask for is refused.

**Updated with it:**
- the prompt-leak pass's rule grams (`app/tests/modules/chat/test_prompt_rule_text.py`);
- the golden prompt (`app/tests/modules/chat/golden/prompt_messages.json`, regenerated with
  `uv run python -m app.tests.modules.chat.test_prompt_golden`; the diff is only the clock
  sentence).

**Tests run** (from `apps/api`):
- chat, services and memory: 10,651 passed;
- `test_battery.py`: 345 passed, 1 expected failure.
- What fails is not this branch's:
  - the database tests error with no Postgres here;
  - 3 tests fail on main too: `test_photo_reference_lookup.py` (2) and
    `test_regenerate_turn_mode.py::test_a_regenerated_yes_still_accepts_the_offer`.

**Not yet done: nobody has checked that the replies actually changed.** The session that wrote
these rules had no model key, so it couldn't replay the chat.

## 4. What you must do

1. **Replay the chat through the real pipeline on this branch, and measure it.**
   - **The key:**
     - You need a model key. Recall calls models through OpenRouter (`OPENROUTER_API_KEY`;
       aliases in `app/models/model_catalog.py`).
     - Never create `apps/api/.env`, and never ask the owner to paste a key into chat. In a
       cloud session, use the environment's credential form (`request_credential` for host
       `openrouter.ai`).
     - Without a key, stop and say so. Never fake replies with a stand-in and call it
       Recall.
   - **The run:**
     - Run the 80 `user` lines in order as one chat, history kept, through the same path a
       real turn takes: the prompt builder, the turn's read, the model, the finalize passes and
       the summary fold.
     - Start from `harness.py`'s `route_case` and `saved_reply` and the way
       `app/tests/behavior/stem_sweep.py` and `formal_eval.py` drive turns. You need the model
       call that the offline harness mocks.
     - Use the owner's settings for this chat: tone casual, Emoji "Lots" (`emoji_use="more"`),
       first name Bini, locale en.
   - **The output:** the before/after document in the same shape as the owner's: the table
     above with a third column for this branch, then every turn's message, before, and after.
     Count the patterns with one script, and commit the script and the result under
     `docs/qa/`.
2. **Meet or beat the target column. Fix what still misses, the same way:**
   - change the rule that causes it, found by reading the real prompt;
   - add a test that pins the rule;
   - never add a word or phrase list that decides intent. The owner's rule is "the model reads,
     the server checks".
   - **Measure each fix.** Re-run the replay after each change, and keep a change only if it
     moves its pattern without breaking another.
3. **Check the replay's own new mistakes.** The lost fixes' replay had these; make sure this
   branch doesn't:
   - **turn 67:** "Dude we are wife and husband…" got "I get why you're frustrated, Dude": a word
     read as a name;
   - **turn 62:** "We spent the money" mixed up the $300,000 and the $500,000;
   - **turn 75:** "Before we finish?" got "Sure, we can stop here": a question read as a goodbye;
   - **turns 71–79:** "I'll skip that part" every turn, sometimes with nothing else, or "Hope
     the rest of your day goes well" mid-scene. Skipping detail is right; a reply that is only
     that line six times in a row is not.
   - **after turn 69:** "Are you okay, do you feel safe with her?" should be asked once, and
     **taken back up** if he later says he isn't safe.
4. **Keep everything else green.** From `apps/api`, run:
   - `uv run pytest app/tests/modules/chat app/tests/services app/tests/modules/memory -q`;
   - `uv run pytest app/tests/behavior/test_battery.py app/tests/behavior/test_sweep.py -q`;
   - ruff, ruff format and mypy on what you change.

   The decision diff (`uv run python -m app.tests.behavior.decisions dump` before and after)
   must show no routing or rule-name change. These are wording changes only.
5. **Open the PR.**
   - Title: "Chat: a personal conversation answered like a friend (measured on an 80-message
     chat)".
   - Body: the three-column table, the rules changed, and the test results.
   - Label it `review`, then `review-gemini` 3 minutes later. Don't merge.
   - Commits end with "Co-Authored-By: Claude <noreply@anthropic.com>"; the PR body ends with
     "🤖 Generated with [Claude Code](https://claude.com/claude-code)".

## 5. Owner decisions to respect

- **A one-line closing summary is wanted:** ending on the point is fine; ending on an offer
  isn't.
- **The model reads, the server checks:** no intent word lists.
- **Real personal help, never a refusal of ordinary personal topics** (`PERSONAL_HELP_RULE`).
- **Safety is never weakened for self-harm:** a real threat still gets clear steps and 911.
- **The Emoji setting is the user's:** "Lots" stays plenty; it just has to fit.
