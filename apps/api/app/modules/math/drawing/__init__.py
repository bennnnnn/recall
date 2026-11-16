"""A picture the reply model describes and the server checks and draws (the ```draw fence).

Owner decision (2026-11-14): the reply model decides what a picture shows; the server checks
every item against the question and works out every coordinate; an item that fails its
check is left out, never drawn wrong. ``vocabulary`` is the closed list of items a
description may hold, ``question`` what the question states, ``build`` the check and the
drawing (a ```geometry ``figure``), and ``contract`` the prompt that asks for one.
"""
