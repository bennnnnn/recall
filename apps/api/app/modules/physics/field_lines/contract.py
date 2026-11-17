"""The prompt contract that asks a physics reply to describe its field picture.

Added beside the message on a physics turn whose read says it asks to see a diagram and
no solve drew one (chat's ``drawing_turn``). The reply says what to draw in a ```draw block
of a closed vocabulary (``describe``), and the server traces it (``picture``); a picture the
vocabulary cannot say is described in words. Owner decision (2026-11-14): the reply model
decides what a picture shows, the server checks every item and computes every coordinate.
"""

from app.services.picture_copy import PICTURE_PLACEMENT_RULE

FIELD_DRAW_CONTRACT = (
    "Picture for this question: when it asks to see the pattern of an electric field "
    "(field lines) around point charges or between two charged plates, describe each "
    "picture in its own ```draw block after your answer (one for each part that asks for "
    "one); the app checks it and draws the field lines from it. Write only JSON:\n"
    "- point charges, in a row, left to right in the order the question names them: "
    '{"kind":"field","part":"a","charges":[{"sign":"+"},{"sign":"-"}]}; give a charge an '
    '"amount" only when the question states its size, as the question writes it ("2q", '
    '"3 μC"), and then give every charge one;\n'
    '- two oppositely charged parallel plates: {"kind":"field","part":"c","plates":'
    '{"positive":"top"}};\n'
    '- "part" is the letter of the question\'s part that picture answers; leave it out '
    "when the question has no parts.\n"
    "At most three charges, all in one row. Any other picture (another arrangement, a "
    "magnetic field, a circuit) gets no block: say in words what it shows. Never draw a "
    "field or any other picture in characters, a table, Mermaid, SVG or a code block. "
    f"{PICTURE_PLACEMENT_RULE}"
)
