"""The prompt contract that asks a physics reply to describe its scene in a ```draw block.

Added with the field contract (``field_lines.contract``) on a physics turn no solve drew a
picture for. The reply names the scene and the question's values it uses; the server
checks each against the question and draws the scene its solver draws
(``scene_drawing``). A value the question does not state, or a situation the vocabulary
does not hold, draws nothing.
"""

SCENE_DRAW_CONTRACT = (
    "Picture of the setup: when the question is a problem about one of these situations, "
    "always end your reply with one ```draw block describing its setup (one for the whole "
    "question, also when it has parts), whether or not it asks for a picture; the app "
    "checks it and draws the scene. A ```draw block is no drawing of yours: the rule "
    "against drawing a situation yourself stays, and this block is how the app draws it. "
    "Write "
    'only JSON: {"kind":"scene","scene":"<name>","values":{"<part>":"<value '
    'with its unit, as the question states it>"}}. Give only values the question states, '
    "never one you worked out, and never a coordinate; the scene uses every value the "
    "question states for its parts, or it is another situation and gets no block. Scenes "
    "and their parts (* the scene "
    "needs it):\n"
    "- projectile: speed*, angle* (above the horizontal; left out, with "
    '"horizontal": true, when it is launched horizontally), height (of the launch above '
    "the landing ground), g;\n"
    "- incline (a block sliding down a slope with friction): angle*, friction* (the "
    "coefficient), mass, g;\n"
    "- atwood (two masses hanging over one pulley): mass1*, mass2*;\n"
    "- collision (two bodies on a line, moving the same way): mass1*, speed1* (of the "
    "moving or faster body), mass2*, speed2 (left out when it is at rest), and "
    '"sticks": true when they stick together or "elastic": true when the collision is '
    "elastic;\n"
    "- pendulum: length*;\n"
    "- orbit (a satellite round a planet): altitude* (above the surface), planet_mass, "
    "planet_radius;\n"
    "- refraction (light entering a material): angle* (of incidence), index* (of the "
    "material it enters), index_from (of the material it comes from, when not air);\n"
    "- lens (one converging lens): focal_length*, object_distance*, object_height;\n"
    "- banked_curve (a car on a banked road, seen from behind): angle* (of the bank).\n"
    "Any other situation (two lenses, a diverging lens, a projectile landing on a slope or "
    "launched downward, a block pushed or sliding up, a block at rest, a pulley on a slope "
    "or with its own mass, a head-on or 2-D collision, a spring, a wave, a loop, a conical "
    "pendulum, a charge in a magnetic field) gets no scene block."
)
