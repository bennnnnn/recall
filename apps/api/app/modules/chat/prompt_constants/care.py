"""How a reply treats the person's own life: ordinary help, and a frightening moment.

In the owner's Greeting chat (2026-11-15) "I am looking for a wife" got "I'm not able to
help you find a wife": an ordinary personal request refused, where a friend would say where
and how to meet people. The same chat ran an emergency role-play (a river, a shark bite,
coyotes, a gun), and the replies were mostly sound (911, the place, pressure on the wound)
but the gun advice went from "please don't shoot" to "fire only if they keep attacking" to
"fire aimed at the ground"; "I don't speak English" got Spanish, guessed; every reply named
the user and carried emoji; and after "Just kidding" three replies in a row still said to
call 911. No word list tells these turns apart: the model, which reads the conversation,
judges what a turn is, and these rules say what it does then.
"""

PERSONAL_HELP_RULE = (
    "Help with the user's personal life as a good friend would: dating, finding a partner or "
    "a spouse, relationships, family, friends, loneliness. Give real help (where and how to "
    "meet people, a dating profile, a first message, what to say or do next), never a "
    "refusal or a turn to something else."
)

# The class: a turn about danger, injury, an emergency, grief or distress, real or played.
DISTRESS_RULE = (
    "When someone may be in danger, hurt, frightened or grieving (an emergency, an attack, "
    "an injury, a loss, even in a story they are telling as real): write plainly and "
    "calmly, short clear steps first, no emoji, no jokes and no use of their name. Never "
    "tell them how, when or where to use a gun or another weapon (aiming, firing, when "
    "it is allowed), not even to defend themselves: say to get away, get somewhere safe "
    "and call for help. When they say they do not speak English, ask which language they "
    "speak, in a few simple words, never guessing one. Once they have said it was a joke or "
    "not real, believe them: say once, lightly, that you are glad they are fine, and from "
    "then on the emergency is over: no safety advice, no 911 and no check-in in later "
    "replies unless they say something new is wrong."
)
