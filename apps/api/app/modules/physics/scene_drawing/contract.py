"""The prompt contract that asks a physics reply to describe its scene in a ```draw block.

Added with the field contract (``field_lines.contract``) on a physics turn no solve drew a
picture for. The reply names the scene and the question's values it uses; the server
checks each against the question and draws the scene its solver draws
(``scene_drawing``). A value the question does not state, or a situation the vocabulary
does not hold, draws nothing.
"""

# The scenes a block may name and the values each takes: the reply's contract below, and the
# physics figure read's (``figure_read``), which writes the same block beside the reply.
SCENE_VOCABULARY = (
    '{"kind":"scene","scene":"<name>","values":{"<part>":"<value '
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
    "- banked_curve (a car on a banked road, seen from behind): angle* (of the bank);\n"
    "- table_pulley (a block on a smooth level table pulled over a pulley at its edge by a "
    "hanging mass): mass1* (of the block on the table), mass2* (of the hanging mass).\n"
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

SCENE_DRAW_CONTRACT = (
    "Picture of the setup: when the question is a problem about one of these situations, "
    "always end your reply with one ```draw block describing its setup (one for the whole "
    "question, also when it has parts), whether or not it asks for a picture; the app "
    "checks it and draws the scene. A ```draw block is no drawing of yours: the rule "
    "against drawing a situation yourself stays, and this block is how the app draws it. "
    "Write only JSON: " + SCENE_VOCABULARY
)

# The forces on one body, written by the figure read (``figure_read``): the server draws the
# free-body diagram from its own reading of the question (``physics.force_pictures``) only
# when the forces it reads are the ones named here (``forces``).
FORCES_VOCABULARY = (
    "The forces on one body (a free-body diagram), when no scene above draws its setup: "
    '{"kind":"forces","body":"<the body, one word as the question names it: box, block, '
    'car, ball, crate, lorry>","forces":["<each force acting on that body, one word each: '
    'weight, normal, friction, tension, push, drag>"]}. A pull by a rope or a string is '
    "tension; an applied push, a driving force or a thrust is push; air resistance is "
    "drag. Only the forces acting at the moment the question describes, none it does not "
    "state or imply: no friction on a smooth or frictionless surface, no drag unless air "
    "resistance acts."
)

# A bar or rod with forces at points along it (moments), checked value by value (``beam``).
BEAM_VOCABULARY = (
    "A bar, rod, beam or see-saw with forces or masses at points along it (moments), its "
    'marks left to right: {"kind":"beam","marks":[{"name":"<the point\'s letter as the '
    'question names it, or empty>","gap":"<its distance from the mark before it, as the '
    'question states it; left out for the first mark>","pivot":true (only the pivot, axis '
    'or balance point),"forces":[{"name":"<the force\'s letter, or empty>","size":"<its '
    "value with its unit as stated: a force, or a mass hung there; or the letter of an "
    'unknown force>","direction":"up" or "down"}]}]}. "at" in place of "gap" is a '
    'distance the question measures from the first mark ("50 cm from P"). A distance the '
    'question asks for is its letter ("x"). Only forces straight up or down: a force at '
    "another angle, a couple or two bars gets no block."
)

# Beside a physics message asking to see a picture: the question's own arrows, which the
# server checks one by one and lays out (``vectors``).
VECTORS_DRAW_CONTRACT = (
    "Arrows of the question's own values, when no scene above draws its setup (two bodies "
    "heading for one point or for each other before they collide, forces on one point, a "
    "journey in legs, a boat or plane and the current or wind): one ```draw block, "
    '{"kind":"vectors","layout":"bodies" (each body with its arrow, as before a collision) '
    'or "tail" (every arrow from one point) or "chain" (head to tail, legs of a journey),'
    '"quantity":"velocity" or "force" or "displacement" or "momentum","arrows":[{"name":'
    '"<the body or force as the question names it>","size":"<its value with its unit, as '
    'the question states it>","direction":"<as the question states it for that value: '
    "north, south-west, 30° east of north, N30°E, bearing 060°, left, right, up, down, 30° "
    "above the horizontal, a wind from the west; or 90° to <an earlier arrow's name> for an "
    "angle the question "
    'states between them; left out when it states none>","mass":"<the body\'s mass as '
    'stated; bodies only>"}],"resultant":true (tail or chain, when the question asks for '
    'the resultant),"after":"together" (bodies, when they stick together after colliding)}. '
    "Every arrow of that quantity the question gives a direction, never a value you worked "
    "out, and for bodies only their velocities before they collide; the app works out and "
    'draws the rest. A vector the question writes by its components ("A [4 5] N", '
    '"velocity [5 2] m/s") is {"name":"A","components":"[4 5]"}, in place of size and '
    "direction, every written vector of that quantity one arrow."
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
