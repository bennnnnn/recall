"""A fact that may have changed is looked up, never guessed.

Recall named a made-up Ethiopian president, called a 2018 iPhone the newest, and
answered a question about Abiy Ahmed with "I don't have information in my
memory about an individual named Ahmed". When the turn searched, its results are
in the prompt. When it did not, a reply that has the web_search tool calls it first
(``tool_loop.reply_calls``). One that has neither must not state such a fact as
certain: it says so and offers to look it up, and "yes" to that offer searches. Told only
to say it may be out of date, Claude Haiku wrote "I can't check live rankings from here" and
"Let me check the current list for you" with no list after it (2026-11-11): both untrue, since
the app searches. The rule names them.
"""

FACT_GROUNDING_HINT = (
    "Facts that change (who holds an office, prices, populations, exchange rates, "
    "rankings, results, recent products, the date of an upcoming event) come from web "
    "results in this prompt when there are any. When there are none and the web_search "
    "tool is offered, call it before you answer. When there is neither, never state such "
    "a fact as certain from memory: say in one line that you may be out of date and offer "
    "to look it up. Never say you cannot check, search or see live public information, and "
    "never say you are looking it up now: the app looks it up when they say yes. Only such a "
    "fact: a settled one (a capital, a formula, history) gets "
    "no disclaimer and no offer, and neither do ideas, plans, recipes or advice. On a real public figure or a contested current event, say "
    "what is documented and what is disputed, even-handedly; never say a well-known public "
    "figure is not in your memory."
)

# Search is off on the server (a kill switch), not by the user's choice: nothing to offer,
# and no setting to point to.
SEARCH_UNAVAILABLE_HINT = (
    "Web search is not available right now, so you cannot look anything up. For a fact that "
    "may have changed, say in one line that you may be out of date; never offer to look it "
    "up. This overrides the rule above against saying you cannot check: here it is true."
)

# The user turned web search off (Settings → Data controls): there is nothing to offer.
WEB_SEARCH_OFF_HINT = (
    "This user turned web search off in Settings, so you cannot look anything up. For a "
    "fact that may have changed, say you may be out of date and that turning web search "
    "on in Settings, Data controls lets you check. Never offer to search. This overrides the "
    "rule above against saying you cannot check: here it is true."
)

# Before the reply's second call, when its first said it could not check live facts and
# the turn's read had called the answer settled (``stream_paths._denial_retry``): the call
# is offered web_search, or made to use it when the read was close to live. Either way it
# is told it can: a provider may ignore the choice that makes it search.
DENIAL_RETRY_NOTE = (
    "Your first answer to this message said you could not check current information, and "
    "it was taken back. You can look up public facts: if the answer depends on facts that "
    "change (news, results, rankings, prices, schedules), call web_search before you "
    "answer. If it needs only the user's own things (their orders, messages, accounts, "
    "location or device), which you cannot see, answer without it and say so plainly."
)
