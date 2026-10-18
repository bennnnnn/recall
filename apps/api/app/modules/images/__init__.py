"""Image generation and reference-photo lookup.

Importing a submodule must not pull the other product's service graph.
"""

# The chat turn checks both intents and runs generation or lookup in place of a reply;
# answer_photo puts a real photo above an ordinary reply.
_MODULE_EXPORTS = ("answer_photo", "gen_intent", "generation", "intent", "lookup_intent", "search")
