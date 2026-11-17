"""The prompt contract that asks a physics reply to describe its scene in a ```draw block.

Added with the field contract (``field_lines.contract``) on a physics turn no solve drew a
picture for. The reply names the scene and the question's values it uses; the server
checks each against the question and draws the scene its solver draws
(``scene_drawing``). A value the question does not state, or a situation the vocabulary
does not hold, draws nothing.
"""

SCENE_DRAW_CONTRACT = (
    "Picture of the setup: when the question is a problem about one of these situations, "
    "describe one picture of its setup in one ```draw block after your answer (one for the "
    "whole question, also when it has parts); the app checks it and draws the scene. Write "
    'only JSON: {"kind":"scene","scene":"<name>","values":{"<part>":"<value '
    'with its unit, as the question states it>"}}. Give only values the question states, '
    "never one you worked out, and never a coordinate. Scenes and their parts (* the scene "
    "needs it):\n"
    "- projectile: speed*, angle* (above the horizontal), height (of the launch above the "
    "landing ground), g;\n"
    "- incline (a block sliding down a slope with friction): angle*, friction* (the "
    "coefficient), mass, g;\n"
    "- atwood (two masses hanging over one pulley): mass1*, mass2*;\n"
    "- collision (two bodies on a line): mass1*, speed1*, mass2*, speed2 (left out when it "
    'is at rest), and "sticks": true when they stick together or "elastic": true when '
    "the collision is elastic;\n"
    "- spring (a mass on a spring): spring_constant*, mass*;\n"
    "- pendulum: length*;\n"
    "- orbit (a satellite round a planet): altitude*, planet_mass, planet_radius;\n"
    "- refraction (light entering a material): angle* (of incidence), index* (of the "
    "material it enters), index_from (when it does not come from air);\n"
    "- lens (one converging lens): focal_length*, object_distance*;\n"
    '- standing_wave (a string fixed at both ends): length*, and "harmonic": n when the '
    "question names one.\n"
    "Any other situation (two lenses, a slope that is not a plane, a pulley on a slope, a "
    "2-D collision, a loop, a banked curve) gets no scene block."
)
