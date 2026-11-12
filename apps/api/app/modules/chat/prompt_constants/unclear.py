"""A message whose meaning is unclear: notice it, don't greet past it.

"Bo" got "Hey Bini! How's it going?", as if it were "hi". A person reacts to the
word itself: "Bo? Did you mean something in Amharic, or were you still typing?"
No list of words or length gate decides what is unclear: "gd" is "good" after
"How's it going?" and a puzzle on its own. Only the model sees the conversation,
so every turn carries the rule and the model judges.

"1" and "More on 1" under a numbered list of ways to learn Python got "That's just the
number 1 … were you testing me?" and "checking the time or date?"; "4" under five beginner
mistakes got "Option 4 is a small number" (2026-11-06). A number after a list names its item.

"can u explain it so a 12 year old gets it" right after a worked answer got "which thing do
you want explained?", and "Who created it" after a reply about the square root sign was read
as a question about Recall (2026-11-06). A follow-up that leaves out what it is about is
about the last reply: "it" is its subject, and "a cheaper one?" asks for more of what it
suggested.

Still, on a Pro phone test (2026-11-11), "Top 5 in Ethiopia" right after a list of the world's
top universities got "Do you mean the top 5 universities in Ethiopia, the top 5 tourist sites,
or something else?", and the "Yes" to that got "I'm not sure what you're saying yes to". Asked
the same way, Claude Haiku asked back about "the cheapest one" under five dinner ideas and "the
language" after "Python the language, or the snake?" on every try: the rule opened on when to
ask, and the model named the obvious reading first in its question. The rule now opens on the
conversation filling in what a short message leaves out, takes a reading it would name first as
clear, and reads a reply to its own question as the answer.
"""

UNCLEAR_MESSAGE_HINT = (
    "Read each message as the next turn of this conversation: what a short one leaves out "
    "comes from the turns before it, and the reading the conversation points to is what it "
    "means. A reading you would name first in a question back is clear enough: answer it, "
    "never ask whether they meant it. A short message that points into a list of yours, by "
    'number, place or quality ("1", "more on 4", "#2", "the second one", "the last one", '
    '"the quickest"), means that item of your most recent list: say more about that item, '
    "and never ask what the number means. A follow-up that leaves out what it is about "
    '("explain it so a kid gets it", "who created it", "why is that", "a cheaper one?") is '
    'about your most recent reply: "it" or "that" is what the reply was about, and a '
    "comparison asks for new picks of the kind it suggested, changed that way. One that "
    'names only something new ("and in Peru?", "what about March?") asks your most recent '
    "question again for it. A message after a question you asked is its answer: a word that "
    "matches one of the options you offered picks it, and a yes to a question that offered "
    "readings takes the first one you named. Answer it; never ask which thing they mean, "
    "and never ask the same question again. Only when you cannot tell what a message means "
    "even with the conversation (a typo, an abbreviation, a word in another language, a "
    "message cut off mid-typing, or nothing before it to fill in what it leaves out), do not "
    "guess silently or treat it as a greeting. Reply with one short, casual sentence that "
    "names the one or two readings a person would actually guess (a word in a language they "
    'may speak counts), in your own words, the way a friend texts back: for "gd", whether '
    'they meant "good"; for "Bo", whether they were still typing. That sentence '
    "is the whole reply: no greeting, no name, no list, no bold, no sign-off. When the "
    "conversation makes it clear, take that reading and reply; do not ask (after you asked "
    '"How\'s it going?", "gd" is "good").'
)
