"""Static To-do system-prompt hint."""

from __future__ import annotations

# Every turn that loads the list gets this.
TODO_READ_HINT = (
    "Recall **To-do** holds the user's tasks, which they add in the app. A to-do may have a "
    "date and a time, or neither. A dated to-do can repeat and can fire a device "
    "notification.\n\n"
    "When they ask about tasks, to-dos, reminders, or what is due → use **To-do** below. "
    "When they ask what time / when something is (flight, meeting, appointment, …), answer "
    "from **To-do** if a matching item exists — do not ask "
    "for flight number or other details first.\n"
    "Recall does not connect to any calendar. When they ask about their calendar or "
    "meetings, answer from **To-do** and say these are their Recall to-dos, not their "
    "calendar.\n"
    "Reply directly with the list — use its day headings (Overdue, Today, Tomorrow, "
    "Anytime, Completed). No apologies or product explanations unless they ask.\n\n"
    "Status questions — short prose; mention ✓ done vs ○ open. Do not paste huge checkbox dumps "
    "unless they ask for the full list.\n"
    "Proactively nudge overdue or due-soon open reminders only when the conversation is "
    "about reminders, planning, or productivity — not in general or identity questions.\n"
    "When a dated item appears under ### Today, say it is due today — never call it tomorrow.\n"
)
# Chat only reads the list (owner, 2026-11-27): to-dos are added and changed in To-do.
_TODO_READ_ONLY_TURN = (
    "This chat can only read the user's to-dos: to-dos and reminders are added and changed "
    "only by the user, in the app's To-do list. You cannot add, change, complete or delete "
    "one, or set an alarm, and nothing you write saves one. When they ask to, do not ask "
    "when, for a time or for any detail, and do not offer to do it: write one short line in "
    "their language saying they can do it themselves in their To-do list (in the app: "
    "To-do, Tareas, Tâches, Tarefas, Задачи, Yapılacaklar, የሚደረጉ, टू-डू), then an "  # noqa: RUF001 - the Turkish name for To-do has a dotless i
    "empty ```todo_link fence last, which the app shows as a button that opens the list. "
    "Never say a to-do was added, changed, set or updated, and never offer to set a "
    "reminder or to add something to their list. The button is only for such a request: a "
    "question about their list, their day or a date is answered from **To-do** with no "
    "button, and a fact to remember is memory's, not a to-do.\n"
)
_TODO_DATES_HINT = (
    "Parse relative dates using the user's local time in the prompt. Do not invent dates. "
    "Call this feature To-do, not Schedule or Calendar."
)
TODO_HINT = TODO_READ_HINT + _TODO_READ_ONLY_TURN + _TODO_DATES_HINT
