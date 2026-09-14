"""Images — generating them and looking real ones up.

Two separate products behind similar-sounding names: ``generation`` is
text-to-image (Pro), ``search`` is reference-photo lookup (free and Pro). Each
has an intent detector that mirrors its mobile counterpart —
``gen_intent`` / ``lookup_intent`` — and lookup is checked first so "show me an
ear" is never claimed by generation.
"""
