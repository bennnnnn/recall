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
    "A circuit of resistors on one supply is its own block: "
    '{"kind":"circuit","arrangement":"series" or "parallel","supply":"<the voltage>",'
    '"resistors":["<each resistance, one entry per resistor>"]}. A plane mirror\'s image is '
    '{"kind":"plane_mirror","object_distance":"<only when the question states it>"}. On a '
    'follow-up ("draw it", "draw the circuit for this") the values are the earlier '
    "problem's, as it states them. Never answer a request to draw, show or animate a thing "
    "or a motion with a Mermaid flowchart or boxes and arrows.\n"
    "Any other situation (two lenses, a diverging lens, a projectile landing on a slope or "
    "launched downward, a block pushed or sliding up, a block at rest, a pulley on a slope "
    "or with its own mass, a head-on or 2-D collision, a spring, a wave, a loop, a conical "
    "pendulum, a charge in a magnetic field) gets no scene block."
)

# Beside a physics message asking to see a graph against time: the motion in stages, which
# the server checks and draws (``motion_graph``).
MOTION_DRAW_CONTRACT = (
    "Graph of a motion in stages (speed, velocity, acceleration or distance against time, "
    "when no single formula the question writes gives it): one ```draw block, "
    '{"kind":"motion","graphs":["speed" and/or "acceleration", "velocity", "distance"],'
    '"stages":[{"speed":"<a steady speed>","time":"<how long>"}, {"from":"<speed at its '
    'start>","to":"<speed at its end>","time":"<how long>"}]}, every value as the question '
    'states it with its unit; "0" for a stage at rest; a minus sign on a speed the other '
    "way. Every stage needs its time. The app works out every point and every "
    "acceleration and draws each graph asked; one it cannot draw is said under your reply."
)

# How a reply speaks when it describes a picture: the app shows it, or says it could not.
DESCRIBED_PICTURE_SPEECH = (
    "Never write that a picture, animation or graph is here, shown or coming, and never "
    "mention the ```draw block or what the app may show: the app draws the picture or "
    "says in one line that it could not."
)
