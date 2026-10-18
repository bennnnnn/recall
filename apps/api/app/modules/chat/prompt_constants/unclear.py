"""A message whose meaning is unclear: notice it, don't greet past it.

"Bo" got "Hey Bini! How's it going?", as if it were "hi". A person reacts to the
word itself: "Bo? Did you mean something in Amharic, or were you still typing?"
No list of words or length gate decides what is unclear: "gd" is "good" after
"How's it going?" and a puzzle on its own. Only the model sees the conversation,
so every turn carries the rule and the model judges.
"""

UNCLEAR_MESSAGE_HINT = (
    "If you cannot tell what a message means even with the conversation so far (a typo, "
    "an abbreviation, a word in another language, a message cut off mid-typing), do not "
    "guess silently or treat it as a greeting. React to what they sent and offer your best "
    'one or two readings in one short, warm line ("gd: good, or God, or something else?"; '
    "a word in a language they may speak; or that they were still typing). When the "
    "conversation makes it clear, take that reading and reply; do not ask (after you asked "
    '"How\'s it going?", "gd" is "good").'
)
