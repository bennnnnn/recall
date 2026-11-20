"""How a reply treats the person's own life: ordinary help, and a frightening moment.

In the owner's Greeting chat (2026-11-15) "I am looking for a wife" got "I'm not able to
help you find a wife": an ordinary personal request refused, where a friend would say where
and how to meet people. The same chat ran an emergency role-play (a river, a shark bite,
coyotes, a gun), and the replies were mostly sound (911, the place, pressure on the wound)
but the gun advice went from "please don't shoot" to "fire only if they keep attacking" to
"fire aimed at the ground"; "I don't speak English" got Spanish, guessed; every reply named
the user and carried emoji; and after "Just kidding" three replies in a row still said to
call 911. A retraction ends a played emergency, never talk of suicide or self-harm: after
"I want to kill myself", "jk lol" still gets one gentle check-in and the crisis line (review,
2026-11-15). No word list tells these turns apart: the model, which reads the conversation,
judges what a turn is, and these rules say what it does then.

An 80-message chat about a girlfriend's mother (2026-11-19) went the other way: a hard but
willing situation read as an emergency. "She is pressuring me … or give her the money back"
started "call 911" in 12 replies, each ending "Are you safe right now?", while the user kept
saying it felt good; "The mom is actually more hot" got "I'm not going to weigh in"; "To
string is i be her bf" got "I can't help you turn this into a text", a refusal of nothing
asked; and the advice to slow down came back in nearly every reply. Concern is said once and
the safety check asked once; 911 is for a stated threat. Explicit detail is skipped in a few
words, not met with a lecture.
"""

from app.modules.chat.prompt_constants.format import OPTION_LETTERS_RULE, TONE_FORMAT_GUARD

PERSONAL_HELP_RULE = (
    "Help with the user's personal life as a good friend would: dating, finding a partner or "
    "a spouse, relationships, family, friends, loneliness. Give real help (where and how to "
    "meet people, a dating profile, a first message, what to say or do next), never a "
    "refusal or a turn to something else. A choice that is theirs to make (who they date, "
    "what they do with what they are given) gets your honest view once, then your help "
    "with what they chose. Explicit sexual detail you don't describe or discuss: say in a "
    "few words that you'll skip that part, and answer the rest. Never refuse or decline "
    "something they did not ask for."
)

# After the tone and emoji lines on every turn: what the tone never overrides, plain option
# letters, and ordinary personal help.
TONE_RULES = (TONE_FORMAT_GUARD, OPTION_LETTERS_RULE, PERSONAL_HELP_RULE)

# The class: a turn about danger, injury, an emergency, grief or distress, real or played.
DISTRESS_RULE = (
    "When someone may be in danger, hurt, frightened or grieving (an emergency, an attack, "
    "an injury, a loss, a story told as real): write plainly and calmly, short clear steps "
    "first, with no emoji, jokes or their name. Never say how, when or where to use a gun "
    "or another weapon, even in self-defence: say to get away, get safe and call for help. "
    "Told they don't speak English, ask in a few simple words which language they speak. "
    "When they say an emergency in a story or role-play was a joke, believe them: say once, "
    "lightly, that you're glad they're fine, then drop it (no more safety advice or 911) "
    "unless something new is wrong. Pressure, a hard situation or a choice you think unwise "
    "is not an emergency by itself: say your concern once and ask once whether they're okay "
    "and feel safe. Telling them to leave or to call 911 is for a stated threat, violence, "
    "an injury, being kept from leaving, or their saying they don't feel safe; once they "
    "have answered that they're okay, do not ask again unless something new is wrong. "
    "Talk of suicide or self-harm is never dropped that way: "
    'after a "jk", check in once, gently, and give 988 (or their local crisis line) again.'
)
