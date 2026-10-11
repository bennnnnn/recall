"""Image generation and reference-photo lookup.

Importing a submodule must not pull the other product's service graph.
"""

# The chat turn checks both intents and runs generation or lookup in place of a reply.
_MODULE_EXPORTS = ("gen_intent", "generation", "lookup_intent", "search")
