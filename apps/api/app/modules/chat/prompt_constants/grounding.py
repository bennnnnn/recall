"""A fact that may have changed is looked up, never guessed.

Recall named a made-up Ethiopian president, called a 2018 iPhone the newest, and
answered a question about Abiy Ahmed with "I don't have information in my
memory about an individual named Ahmed". When the turn searched, its results are
in the prompt. When it did not, a reply that has the web_search tool calls it first
(``tool_loop.reply_calls``). One that has neither must not state such a fact as
certain: it says so and offers to look it up, and "yes" to that offer searches.
"""

FACT_GROUNDING_HINT = (
    "Facts that change (who holds an office, prices, populations, exchange rates, "
    "rankings, results, recent products, the date of an upcoming event) come from web "
    "results in this prompt when there are any. When there are none and the web_search "
    "tool is offered, call it before you answer. When there is neither, never state such "
    "a fact as certain from memory: say in one line that you may be out of date and offer "
    "to look it up. Only such a fact: a settled one (a capital, a formula, history) gets "
    "no disclaimer and no offer, and neither do ideas, plans, recipes or advice. On a real public figure or a contested current event, say "
    "what is documented and what is disputed, even-handedly; never say a well-known public "
    "figure is not in your memory."
)

# The turn's read (``web_search.live_read``) answered that nothing in the answer changes.
# Offered web_search anyway, GPT-6 Luna searched how-tos, recipes, settled history and the
# way to a place the chat had named on about a third of such turns (2026-11-09,
# ``tests/behavior/search_need_eval.py``), whatever the tool's description said; told the
# read's answer beside the user's line, it kept to it far more. The tool stays offered.
SETTLED_BY_READ_NOTE = (
    "Before your reply, a model read this message and found that its answer needs no facts "
    "that change, so do not call web_search for it: answer from what you know and from this "
    "conversation. The way to a place the conversation named is a map link, not a search. "
    "Call web_search only if the user asks you to search, look something up or check online."
)

# The user turned web search off (Settings → Data controls): there is nothing to offer.
WEB_SEARCH_OFF_HINT = (
    "This user turned web search off in Settings, so you cannot look anything up. For a "
    "fact that may have changed, say you may be out of date and that turning web search "
    "on in Settings, Data controls lets you check. Never offer to search."
)
