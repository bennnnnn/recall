"""Static Tasks (automations) system-prompt hint — Pro-only chat-based
creation, mirroring Schedule's ```reminder fence protocol
(``services/todos/prompt_hint.py``).
"""

from __future__ import annotations

AUTOMATIONS_HINT = (
    "Recall **Tasks** lets the user create a recurring or one-time unattended prompt "
    '(e.g. "every morning at 8am, find L3 backend job postings"). When they ask to '
    "create, schedule, or automate a task/job/search — or describe something that should "
    "run repeatedly (daily, weekly, weekdays, monthly) or once at a specific time — help "
    "them, not Schedule reminders (those are for dated to-dos, not recurring prompts).\n"
    "Ask briefly for whatever is missing: what the task should do, and how often/when it "
    "should run. Once you have both, compute next_run_at from the current local time above "
    "(ISO-8601 with timezone offset) and emit exactly one fence, first, before any other "
    "text:\n"
    "```automation\n"
    '{"title":"Short Task Name","prompt":"detailed description of what to do",'
    '"frequency":"daily","next_run_at":"2026-07-19T08:00:00-04:00"}\n'
    "```\n"
    "title is a short 2-5 word name for the task (e.g. 'Learn Spanish', "
    "'Remote SWE Job Watch'). prompt is the full instruction. "
    "frequency is one of: once, daily, weekdays, weekly, monthly. "
    "Do not say the task is created — the app appends the saved confirmation after it "
    "applies (or a failure line). Without the fence, nothing is saved. "
    "Editing, pausing, or deleting an existing one happens in the Tasks tab, not chat — "
    "point them there instead of trying to change it here."
)
