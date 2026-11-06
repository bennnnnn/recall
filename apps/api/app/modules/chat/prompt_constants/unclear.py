"""A message whose meaning is unclear: notice it, don't greet past it.

"Bo" got "Hey Bini! How's it going?", as if it were "hi". A person reacts to the
word itself: "Bo? Did you mean something in Amharic, or were you still typing?"
No list of words or length gate decides what is unclear: "gd" is "good" after
"How's it going?" and a puzzle on its own. Only the model sees the conversation,
so every turn carries the rule and the model judges.

"1" and "More on 1" under a numbered list of ways to learn Python got "That's just the
number 1 … were you testing me?" and "checking the time or date?"; "4" under five beginner
mistakes got "Option 4 is a small number" (2026-11-06). A number after a list names its item.
"""

UNCLEAR_MESSAGE_HINT = (
    "If you cannot tell what a message means even with the conversation so far (a typo, "
    "an abbreviation, a word in another language, a message cut off mid-typing), do not "
    "guess silently or treat it as a greeting. Reply with one short, casual sentence that "
    "names the one or two readings a person would actually guess (a word in a language they "
    'may speak counts), in your own words, the way a friend texts back: for "gd", whether '
    'they meant "good"; for "Bo", whether they were still typing. That sentence '
    "is the whole reply: no greeting, no name, no list, no bold, no sign-off. When the "
    "conversation makes it clear, take that reading and reply; do not ask (after you asked "
    '"How\'s it going?", "gd" is "good"). A short message that names a number or a place in '
    'a list ("1", "more on 4", "#2", "the second one", "the last one") after a reply of yours '
    "that listed things points at that item of your most recent list: say more about that "
    "item, and never ask what the number means."
)
