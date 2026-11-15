"""Charts of the user's own data, drawn by the server from numbers it checked.

A bar, pie, line or histogram chart of numbers the user typed was a Vega spec the model
wrote, with numbers nobody checked (owner decision, 2026-11-13). ``read.draw_chart`` reads
the data with one fast structured call, ``grounding`` holds every label and value to the
user's own words, and ``build`` writes one of the shapes the phone draws. A reading that
does not hold draws nothing: a wrong picture is never acceptable.
"""

# What chat asks: the read and its check, and a model's chart read back for the same check.
_MODULE_EXPORTS = ("read", "model_chart")
