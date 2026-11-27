"""Turn classifiers used to pick prompt hints and context load."""

LIGHTWEIGHT_REPLY_HINT = (
    "Reply in one brief sentence. "
    "Do not dig into memory, lists, or projects unless the user asked, and make no "
    "closing offer to help further."
)

PERSONAL_DISCLOSURE_HINT = (
    "Take this message as personal context or a goal, not a task. Your entire reply "
    "must be one or two natural sentences with no heading, list, steps, or action plan. "
    "Acknowledge the update and connect relevant known context only when useful. Do not browse, "
    "draft outreach, recommend next steps, or turn the statement into unsolicited advice. You "
    "may ask one brief follow-up question only if it would genuinely help. When the update "
    "contrasts a current situation with a future goal, explicitly preserve both in the "
    "acknowledgement (currently at X; considering Y) instead of mentioning only the goal."
)


NEW_PROBLEM_HINT = (
    "Make up a NEW problem "
    "of the same kind, with a different scenario and different numbers (harder or "
    "easier if they said so), state it, then solve it. Do not repeat, restate, or "
    "re-answer the previous problem. Making it outranks any rule against adding "
    "examples."
)

CONFIRM_FOLLOW_THROUGH_HINT = (
    "Carry out your last offer now, starting with it: answer this yes as the go-ahead, "
    "not as a greeting or a one-word ack, and don't say they accepted or agreed."
)
