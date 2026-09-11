"""Learning prompt hints — progress in chat, study in the lesson screen."""

DAY_LEARNING_SNAPSHOT_HINT = (
    "When 'Today's learning progress' is in context, those lines are authoritative for the "
    "user's local calendar day. Never reuse yesterday's scores from memory or chat history.\n"
    "Only mention tracks that appear in that block (vocabulary quiz) — never invent another "
    "kind of class if it is not listed.\n"
    "If today's learning progress lists an incomplete goal, mention it briefly. "
    "If it says there is **no active learning class**, do not mention quizzes at all. "
    "If a listed goal is complete, you may note that track only — do not invent incomplete "
    "progress or extra classes."
)
