"""How a reply speaks of a picture the app adds to it: it does not place or promise one.

The app places each picture itself: a solve's scene or figure under the working, a photo or
a painting above the words, and on some turns none at all (a photo search that found
nothing, a painting refused). A reply told where the picture would go, or that one was
coming, said so whatever came: "The circuit diagram is shown above" over a schematic drawn
below it, "The photo below shows a similar arc" over no photo, and "The app will draw the
ray diagram" under the one already drawn (live, 2026-11-15). Chat's multi-part contract, its
note beside a message asking for a solve's picture, and physics' verified visual state it.
"""

from __future__ import annotations

PICTURE_PLACEMENT_RULE = (
    "Never say where a picture is (above, below, here) or that one will be drawn, shown or "
    "attached: the app places its pictures itself, and may add none."
)

# Beside a message asking to see a picture the subject's solve drew ("Draw the ray diagram"
# got a section of its own saying the picture was "drawn in the app above this answer",
# under the diagram drawn below it, live 2026-11-15).
DRAWN_PICTURE_NOTE = (
    "The picture this message asks to see is the app's, drawn from the checked answer and "
    "shown with it. The picture is the whole answer to that request, listed or not: give it "
    "no section, heading, sketch or words of the reply's own. "
    f"{PICTURE_PLACEMENT_RULE}"
)
