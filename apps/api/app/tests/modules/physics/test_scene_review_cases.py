"""Every case of the feat/physics-scenes reviews, refusals included.

The server draws a described scene only when the physics reader's own reading of the
question's setup agrees with it: each value stated and of its part's kind, every other
stated quantity one the scene can leave aside, and the setup (a launch's height and
direction, which body moves, the collision's type, the media, the planet) as the reader the
solvers trust reads it. A setup no reader reads is not drawn: a refusal is always
acceptable; a wrong picture never is.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.physics.scene_drawing.describe import described_scene

# (question, the reply's description without its "kind", drawn)
_CASES: list[tuple[str, dict[str, Any], bool]] = [
    (
        "A block is given a speed of 8 m/s up a 30 degree incline. The coefficient of kinetic friction is 0.2. How far up does it slide?",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.2"}},
        False,
    ),
    (
        "A 4 kg block on a 30 degree incline is connected by a light string over a frictionless pulley at the top of the incline to a hanging 6 kg mass. The coefficient of kinetic friction between the block and the incline is 0.15. Find the acceleration.",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.15", "mass": "4 kg"}},
        False,
    ),
    (
        "A 2 kg cart moving east at 3 m/s collides head-on with a 1 kg cart moving west at 4 m/s. They stick together. Find their common velocity.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg", "speed2": "4 m/s"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 0.3 kg ball on a 1.2 m string moves in a horizontal circle so that the string makes 25 degrees with the vertical (a conical pendulum). Find the tension.",
        {"scene": "pendulum", "values": {"length": "1.2 m"}},
        False,
    ),
    (
        "A ray of light strikes a glass surface (n = 1.5) making an angle of 30 degrees with the surface. Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        False,
    ),
    (
        "A 500 kg satellite orbits 600 km above the Earth's surface. Find its orbital speed.",
        {"scene": "orbit", "values": {"altitude": "600 km"}},
        True,
    ),
    (
        "A ball is thrown at 20 m/s at 60 degrees to the vertical. Find its range.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "60°"}},
        False,
    ),
    (
        "A 5 kg block is pushed up a 25 degree incline by a horizontal force of 60 N. The coefficient of kinetic friction is 0.3. Find its acceleration.",
        {"scene": "incline", "values": {"angle": "25°", "friction": "0.3", "mass": "5 kg"}},
        False,
    ),
    (
        "A block rests on a 20 degree incline; the coefficient of static friction is 0.5. Does it slide?",
        {"scene": "incline", "values": {"angle": "20°", "friction": "0.5"}},
        False,
    ),
    (
        "Masses of 2 kg and 4 kg hang over a pulley with moment of inertia 0.01 kg m^2 and radius 0.1 m. Find the acceleration.",
        {"scene": "atwood", "values": {"mass1": "2 kg", "mass2": "4 kg"}},
        False,
    ),
    (
        "Two masses of 3 kg and 5 kg hang on either side of a light frictionless pulley. Find the acceleration and the speed of the 5 kg mass after it has fallen 1.2 m.",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        False,
    ),
    (
        "A ball is launched horizontally at 15 m/s from a 20 m high table. Find the range.",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "0°", "height": "20 m"}},
        False,
    ),
    (
        "Light travels from glass (n = 1.5) into water (n = 1.33) at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.5", "index_from": "1.33"}},
        False,
    ),
    (
        "Light travels from glass (n = 1.5) into water (n = 1.33) at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.33", "index_from": "1.5"}},
        False,
    ),
    (
        "An object is placed 15 cm in front of a diverging lens of focal length 10 cm. Find the image position.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "15 cm"}},
        False,
    ),
    (
        "An object 2 cm tall is placed 5 cm in front of a converging lens of focal length 10 cm.",
        {
            "scene": "lens",
            "values": {"focal_length": "10 cm", "object_distance": "5 cm", "object_height": "2 cm"},
        },
        False,
    ),
    (
        "A satellite orbits 100 km above the Moon's surface. Find its orbital speed.",
        {"scene": "orbit", "values": {"altitude": "100 km"}},
        True,
    ),
    (
        "A 0.5 kg mass hangs on a spring with k = 200 N/m. It is pulled down 3 cm and released. Find the period. Give the answer in seconds.",
        {"scene": "spring", "values": {"spring_constant": "200 N/m", "mass": "0.5 kg"}},
        False,
    ),
    (
        "A string 1.2 m long is fixed at both ends; the wave speed is 120 m/s. Find the frequency of the second harmonic in seconds^-1.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}, "harmonic": 2},
        False,
    ),
    (
        "A string 1.2 m long vibrates; each oscillation takes 0.01 seconds. Sketch it.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}, "harmonic": 2},
        False,
    ),
    (
        "A curve of radius 80 m is banked at 15 degrees. A 1200 kg car takes it at 20 m/s.",
        {"scene": "banked_curve", "values": {"angle": "15°"}},
        False,
    ),
    (
        "A curve is banked at 15 degrees; the angle between the car's path and north is 30 degrees.",
        {"scene": "banked_curve", "values": {"angle": "15°"}},
        False,
    ),
    (
        "An object 2 cm tall is placed 5 cm in front of a converging lens of focal length 10 cm.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "5 cm"}},
        False,
    ),
    (
        "An object 2 cm tall is placed 15 cm in front of a converging lens of focal length 10 cm.",
        {
            "scene": "lens",
            "values": {
                "focal_length": "10 cm",
                "object_distance": "15 cm",
                "object_height": "2 cm",
            },
        },
        False,
    ),
    (
        "A 2 kg cart moving east at 3 m/s collides head-on with a 1 kg cart moving west at 4 m/s. They stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg", "speed2": "4 m/s"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest. They stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "A 10 g bullet moving at 400 m/s embeds itself in a 2 kg wooden block hanging from a long string.",
        {
            "scene": "collision",
            "values": {"mass1": "10 g", "speed1": "400 m/s", "mass2": "2 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 1 kg ball moving at 2 m/s is struck from behind by a 3 kg ball moving at 5 m/s; the collision is elastic.",
        {
            "scene": "collision",
            "values": {"mass1": "3 kg", "speed1": "5 m/s", "mass2": "1 kg", "speed2": "2 m/s"},
            "elastic": True,
        },
        False,
    ),
    (
        "A 1 kg ball moving at 2 m/s is struck from behind by a 3 kg ball moving at 5 m/s; the collision is elastic.",
        {
            "scene": "collision",
            "values": {"mass1": "1 kg", "speed1": "2 m/s", "mass2": "3 kg", "speed2": "5 m/s"},
            "elastic": True,
        },
        False,
    ),
    (
        "A 5 kg block starts from rest at the top of a 4 m long incline at 35 degrees. The coefficient of kinetic friction is 0.25.",
        {"scene": "incline", "values": {"angle": "35°", "friction": "0.25", "mass": "5 kg"}},
        False,
    ),
    (
        "A 5 kg block starts from rest at the top of a 4 m long incline at 35 degrees. The coefficient of kinetic friction is 0.25.",
        {"scene": "incline", "values": {"angle": "35 degrees", "friction": "0.25", "mass": "5 kg"}},
        False,
    ),
    (
        "A stone is thrown from the top of a 45 m high cliff with a speed of 20 m/s at 30 degrees above the horizontal.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A stone is thrown from the top of a 45 m high cliff with a speed of 20 m/s at 30 degrees above the horizontal. Take g = 10 m/s^2.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at 30 degrees below the horizontal from a 45 m cliff.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at 30 degrees from a 45 m cliff. It lands 2.5 s later.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest. They stick together. Find their speed.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest. They stick together. Find their speed.",
        {
            "scene": "collision",
            "values": {"mass1": "1 kg", "speed1": "3 m/s", "mass2": "2 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 1500 kg car travelling at 20 m/s rear-ends a 1000 kg car. The cars lock together.",
        {
            "scene": "collision",
            "values": {"mass1": "1500 kg", "speed1": "20 m/s", "mass2": "1000 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 1500 kg car travelling at 20 m/s rear-ends a 1000 kg car. The cars lock together.",
        {
            "scene": "collision",
            "values": {"mass1": "1000 kg", "speed1": "20 m/s", "mass2": "1500 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 0.5 kg ball moving at 4 m/s collides elastically with a stationary 1.5 kg ball.",
        {
            "scene": "collision",
            "values": {"mass1": "0.5 kg", "speed1": "4 m/s", "mass2": "1.5 kg"},
            "elastic": True,
        },
        True,
    ),
    (
        "A 0.5 kg ball moving at 4 m/s collides elastically with a stationary 1.5 kg ball.",
        {
            "scene": "collision",
            "values": {"mass1": "1.5 kg", "speed1": "4 m/s", "mass2": "0.5 kg"},
            "elastic": True,
        },
        False,
    ),
    (
        "Masses of 2 kg and 4 kg hang from a string over the 2 kg pulley, a uniform disk. Find the acceleration.",
        {"scene": "atwood", "values": {"mass1": "2 kg", "mass2": "4 kg"}},
        False,
    ),
    (
        "A ray passes from air (n = 1.00) into glass (n = 1.50) at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.50"}},
        False,
    ),
    (
        "Question 3: A 5 kg block slides down a 35 degree incline; the coefficient of kinetic friction is 0.25. Give answers to 2 significant figures.",
        {"scene": "incline", "values": {"angle": "35°", "friction": "0.25", "mass": "5 kg"}},
        False,
    ),
    (
        "A string 1.2 m long is fixed at both ends. Find the first three harmonics' frequencies when the wave speed is 120 m/s.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}, "harmonic": 3},
        False,
    ),
    (
        "A pendulum 2 m long swings. A second pendulum is 0.5 m long.",
        {"scene": "pendulum", "values": {"length": "2 m"}},
        False,
    ),
    (
        "A 1.5 kg puck moving at 4 m/s collides with a 2.5 kg puck at rest. After the collision the 1.5 kg puck moves at 2 m/s at 50 degrees north of east.",
        {
            "scene": "collision",
            "values": {"mass1": "1.5 kg", "speed1": "4 m/s", "mass2": "2.5 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 3 kg ball at 4 m/s hits a 2 kg ball at rest and sticks. Then the 3 kg ball and the 2 kg ball move together.",
        {
            "scene": "collision",
            "values": {"mass1": "3 kg", "speed1": "4 m/s", "mass2": "2 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A projectile is fired at 30 m/s at 40 degrees. The target is at an angle of 10 degrees.",
        {"scene": "projectile", "values": {"speed": "30 m/s", "angle": "40°"}},
        False,
    ),
    (
        "A spring (k = 100 N/m) is compressed 0.2 m and launches a 0.5 kg ball.",
        {"scene": "spring", "values": {"spring_constant": "100 N/m", "mass": "0.5 kg"}},
        False,
    ),
    (
        "An object is placed 15 cm in front of a convex mirror of focal length 10 cm. Find the image.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "15 cm"}},
        False,
    ),
    (
        "An object is placed 15 cm in front of a concave lens? No: a convex lens of focal length 10 cm.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "15 cm"}},
        False,
    ),
    (
        "An open pipe 0.85 m long sounds its fundamental. The speed of sound is 340 m/s.",
        {"scene": "standing_wave", "values": {"length": "0.85 m"}},
        False,
    ),
    (
        "A pipe closed at one end is 0.5 m long; find the fundamental frequency if sound travels at 340 m/s.",
        {"scene": "standing_wave", "values": {"length": "0.5 m"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at 60 degrees from vertical. Find its range.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "60°"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at an angle of elevation 60 degrees measured off the vertical axis.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "60°"}},
        False,
    ),
    (
        "A light ray strikes a glass block (n = 1.5) at 30 degrees to the plane of the block. Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        True,
    ),
    (
        "A 2 kg block is released on a 30 degree incline with a coefficient of kinetic friction of 0.7.",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.7", "mass": "2 kg"}},
        False,
    ),
    (
        "A satellite orbits Jupiter at an altitude of 1000 km. Compare its speed with one orbiting Earth at the same height.",
        {"scene": "orbit", "values": {"altitude": "1000 km"}},
        False,
    ),
    (
        "A satellite orbits the Moon 100 km above its surface; the Moon orbits the Earth.",
        {"scene": "orbit", "values": {"altitude": "100 km"}},
        False,
    ),
    (
        "A 2 kg ball collides with a 1 kg ball at 3 m/s and they stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "1 kg", "speed1": "3 m/s", "mass2": "2 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 2 kg ball collides with a 1 kg ball at 3 m/s and they stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A ball is thrown at 25 m/s at 40 degrees above the horizontal. How far does it travel horizontally before landing?",
        {"scene": "projectile", "values": {"speed": "25 m/s"}, "horizontal": True},
        False,
    ),
    (
        "A stone is thrown horizontally at 15 m/s from a 20 m high cliff. A second stone is thrown at 15 m/s at 30 degrees.",
        {
            "scene": "projectile",
            "values": {"speed": "15 m/s", "height": "20 m"},
            "horizontal": True,
        },
        False,
    ),
    (
        "A 4 kg cart moving at 6 m/s catches up with a 2 kg cart moving at 2 m/s in the same direction. They stick.",
        {
            "scene": "collision",
            "values": {"mass1": "4 kg", "speed1": "6 m/s", "mass2": "2 kg", "speed2": "2 m/s"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 4 kg cart moving at 6 m/s collides with a 2 kg cart that moves away at 2 m/s in the same direction as the first did before it reversed. They stick.",
        {
            "scene": "collision",
            "values": {"mass1": "4 kg", "speed1": "6 m/s", "mass2": "2 kg", "speed2": "2 m/s"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 0.5 kg mass on a spring with k = 200 N/m bobs up and down.",
        {"scene": "spring", "values": {"spring_constant": "200 N/m", "mass": "0.5 kg"}},
        False,
    ),
    (
        "A 0.5 kg ball is kicked at 20 m/s at 30 degrees above the horizontal. Find its range.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°"}},
        True,
    ),
    (
        "A ball is kicked at 20 m/s at 30 degrees above the horizontal. Find its range and the time it takes. Take g = 9.8 m/s^2.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "g": "9.8 m/s^2"}},
        True,
    ),
    (
        "A projectile is launched at 30 m/s at 40 degrees above the horizontal. Find its maximum height.",
        {"scene": "projectile", "values": {"speed": "30 m/s", "angle": "40°"}},
        True,
    ),
    (
        "A ball is thrown at 15 m/s at an angle of 35 degrees to the horizontal. Where is it after 1.5 s?",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "35°"}},
        False,
    ),
    (
        "A 10 kg box slides down a 30 degree ramp. The coefficient of kinetic friction is 0.2. Take g = 9.8 m/s^2. Find its acceleration.",
        {
            "scene": "incline",
            "values": {"angle": "30°", "friction": "0.2", "mass": "10 kg", "g": "9.8 m/s^2"},
        },
        True,
    ),
    (
        "A 10 kg box slides down a 30 degree ramp with coefficient of kinetic friction 0.2. How fast is it going after 3 s?",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.2", "mass": "10 kg"}},
        False,
    ),
    (
        "A 2 kg block slides down a rough plane inclined at 25 degrees (coefficient of friction 0.3). Find the acceleration.",
        {"scene": "incline", "values": {"angle": "25°", "friction": "0.3", "mass": "2 kg"}},
        True,
    ),
    (
        "Two masses, 3 kg and 5 kg, are connected by a light string over a frictionless pulley. Find the acceleration and the tension. (g = 9.8 m/s^2)",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        False,
    ),
    (
        "An Atwood machine has masses of 3 kg and 5 kg. The system is released from rest. How far does the 5 kg mass fall in 2 s?",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        False,
    ),
    (
        "A 3 kg mass and a 5 kg mass hang from the ends of a string over a pulley. Find the acceleration of the masses.",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        True,
    ),
    (
        "A simple pendulum is 1.5 m long. Find its period. (g = 9.81 m/s^2)",
        {"scene": "pendulum", "values": {"length": "1.5 m"}},
        False,
    ),
    (
        "A 1500 kg car moving at 20 m/s collides with a stationary 1000 kg car and they lock bumpers.",
        {
            "scene": "collision",
            "values": {"mass1": "1500 kg", "speed1": "20 m/s", "mass2": "1000 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "A 2 kg cart moving to the right at 3 m/s hits a 1 kg cart at rest and they stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "Light passes from air into glass of refractive index 1.5 at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.5"}},
        False,
    ),
    (
        "A ray of light travels from air into water (n = 1.33) at an angle of incidence of 35 degrees.",
        {"scene": "refraction", "values": {"angle": "35°", "index": "1.33"}},
        False,
    ),
    (
        "An object is placed 30 cm from a converging lens of focal length 10 cm. Find the image distance.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "30 cm"}},
        True,
    ),
    (
        "An object is placed 30 cm from a lens of focal length 10 cm. Find the image distance.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "30 cm"}},
        True,
    ),
    (
        "A satellite orbits 400 km above the Earth. Find its orbital speed.",
        {"scene": "orbit", "values": {"altitude": "400 km"}},
        True,
    ),
    (
        "A 1000 kg satellite orbits 400 km above the Earth. Find its orbital speed.",
        {"scene": "orbit", "values": {"altitude": "400 km"}},
        True,
    ),
    (
        "A satellite orbits 300 km above Mars, whose mass is 6.42 x 10^23 kg. Find its orbital speed.",
        {"scene": "orbit", "values": {"altitude": "300 km", "planet_mass": "6.42 x 10^23 kg"}},
        False,
    ),
    (
        "A satellite orbits 300 km above Mars (mass 6.42 x 10^23 kg, radius 3390 km). Find its orbital speed.",
        {
            "scene": "orbit",
            "values": {
                "altitude": "300 km",
                "planet_mass": "6.42 x 10^23 kg",
                "planet_radius": "3390 km",
            },
        },
        False,
    ),
    (
        "A satellite orbits 300 km above Mars, radius 3390 km. Compare with Earth.",
        {"scene": "orbit", "values": {"altitude": "300 km", "planet_radius": "3390 km"}},
        False,
    ),
    (
        "A probe orbits 500 km above a planet of radius 3000 km. Earth's g is 9.8 m/s^2 for comparison.",
        {"scene": "orbit", "values": {"altitude": "500 km", "planet_radius": "3000 km"}},
        False,
    ),
    (
        "A ball is thrown horizontally from the top of a 20 m cliff. How long does it take to land?",
        {"scene": "projectile", "values": {"height": "20 m"}, "horizontal": True},
        False,
    ),
    (
        "A ball rolls horizontally off a 1.2 m high table and lands. Find the time.",
        {"scene": "projectile", "values": {"height": "1.2 m"}, "horizontal": True},
        False,
    ),
    (
        "A plane flying horizontally at 100 m/s at a height of 500 m drops a package.",
        {
            "scene": "projectile",
            "values": {"speed": "100 m/s", "height": "500 m"},
            "horizontal": True,
        },
        False,
    ),
    (
        "A ball is thrown down at an angle of 30 degrees at 15 m/s from the top of a 45 m cliff.",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A stone is thrown at 15 m/s at 30 degrees toward the sea from a 45 m cliff, aimed down.",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at 50 degrees and lands on the roof of a 10 m high building. Find the time of flight.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "50°", "height": "10 m"}},
        False,
    ),
    (
        "A ball is kicked from the ground at 20 m/s at 50 degrees over a 10 m tall wall.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "50°", "height": "10 m"}},
        False,
    ),
    (
        "A ball is thrown from the edge of a cliff at 15 m/s at 30 degrees above the horizontal. It hits the ground below after 4 s. How high is the cliff?",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "30°"}},
        False,
    ),
    (
        "A ball is kicked at 20 m/s at 30 degrees above the horizontal and is in the air for 3 s.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°"}},
        False,
    ),
    (
        "A 1.5 kg block is dropped from 0.8 m onto a spring (k = 1200 N/m) resting on the floor. Find the maximum compression.",
        {"scene": "spring", "values": {"spring_constant": "1200 N/m", "mass": "1.5 kg"}},
        False,
    ),
    (
        "A 2 kg block moving at 3 m/s on a frictionless table hits a spring with k = 500 N/m. Find the maximum compression.",
        {"scene": "spring", "values": {"spring_constant": "500 N/m", "mass": "2 kg"}},
        False,
    ),
    (
        "A satellite 300 km above the Martian surface: is it faster or slower than one 300 km above Earth?",
        {"scene": "orbit", "values": {"altitude": "300 km"}},
        False,
    ),
    (
        "A moon of Jupiter orbits at a height of 500 km; how does its speed compare with a satellite at the same height above Earth?",
        {"scene": "orbit", "values": {"altitude": "500 km"}},
        False,
    ),
    (
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest. They do not stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest. The collision is not elastic.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "elastic": True,
        },
        False,
    ),
    (
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest and bounces back; they move apart. Is the collision elastic?",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "elastic": True,
        },
        False,
    ),
    (
        "A 2 kg block on a frictionless table moving at 3 m/s hits a 1 kg block at rest and they stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "A light ray in glass (n = 1.5) reaches the surface with water above it at an angle of incidence of 30 degrees; the water has n = 1.33.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.33", "index_from": "1.5"}},
        False,
    ),
    (
        "Light passes from air into glass (n = 1.5); its angle of refraction is 30 degrees. Find the angle of incidence.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        False,
    ),
    (
        "A ray in air strikes glass (n = 1.5); the refracted ray makes 30 degrees with the normal.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        False,
    ),
    (
        "An object 2 cm tall is placed 15 cm from a converging lens of focal length 10 cm. A screen is 30 cm away.",
        {
            "scene": "lens",
            "values": {
                "focal_length": "10 cm",
                "object_distance": "15 cm",
                "object_height": "2 cm",
            },
        },
        False,
    ),
    (
        "A converging lens has a focal length of 10 cm. An object is 15 cm from the image formed? no - an object is placed 15 cm from the lens.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "15 cm"}},
        False,
    ),
    (
        "A 5 kg block is placed on a 30 degree incline; the coefficient of kinetic friction is 0.2. It is given a push down the slope at 2 m/s.",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.2", "mass": "5 kg"}},
        False,
    ),
    (
        "A 5 kg block on a 30 degree incline is released; the coefficient of kinetic friction is 0.2. A force of 10 N acts on it.",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.2", "mass": "5 kg"}},
        False,
    ),
    (
        "A projectile accelerates at 10 m/s^2 for 2 s and is then launched at 20 m/s at 30 degrees.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°"}},
        False,
    ),
    (
        "On the Moon (g = 1.6 m/s^2) a ball is thrown at 10 m/s at 45 degrees.",
        {"scene": "projectile", "values": {"speed": "10 m/s", "angle": "45°"}},
        False,
    ),
    (
        "A ball is kicked at 20 m/s at an angle of 30 degrees to the horizontal. Find its range.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°"}},
        True,
    ),
    (
        "A projectile is fired with an initial velocity of 50 m/s at an angle of 37 degrees above the horizontal. Find the maximum height.",
        {"scene": "projectile", "values": {"speed": "50 m/s", "angle": "37°"}},
        True,
    ),
    (
        "A football is kicked with a velocity of 25 m/s at 40 degrees. How far does it travel?",
        {"scene": "projectile", "values": {"speed": "25 m/s", "angle": "40°"}},
        True,
    ),
    (
        "A cannonball is fired at 100 m/s at an angle of elevation of 45 degrees. Find its range.",
        {"scene": "projectile", "values": {"speed": "100 m/s", "angle": "45°"}},
        True,
    ),
    (
        "A ball is thrown horizontally at 10 m/s from the top of a 20 m tall building. How far from the base does it land?",
        {
            "scene": "projectile",
            "values": {"speed": "10 m/s", "height": "20 m"},
            "horizontal": True,
        },
        True,
    ),
    (
        "A stone is thrown horizontally from a cliff 45 m high with a speed of 12 m/s.",
        {
            "scene": "projectile",
            "values": {"speed": "12 m/s", "height": "45 m"},
            "horizontal": True,
        },
        False,
    ),
    (
        "A ball is projected at 30 m/s at 60 degrees to the horizontal from the top of a 20 m high tower.",
        {"scene": "projectile", "values": {"speed": "30 m/s", "angle": "60°", "height": "20 m"}},
        False,
    ),
    (
        "A 10 kg box slides down a ramp inclined at 30 degrees. The coefficient of kinetic friction is 0.2. Find its acceleration.",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.2", "mass": "10 kg"}},
        True,
    ),
    (
        "A block slides down a 40 degree incline with a coefficient of kinetic friction of 0.3. What is its acceleration?",
        {"scene": "incline", "values": {"angle": "40°", "friction": "0.3"}},
        True,
    ),
    (
        "A 3 kg block slides down a rough inclined plane of angle 30 degrees. If the coefficient of kinetic friction is 0.25, find the acceleration of the block.",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.25", "mass": "3 kg"}},
        True,
    ),
    (
        "A 2 kg box on a 25 degree slope with coefficient of kinetic friction 0.1 accelerates down. Find a.",
        {"scene": "incline", "values": {"angle": "25°", "friction": "0.1", "mass": "2 kg"}},
        True,
    ),
    (
        "Two masses of 3 kg and 5 kg are connected by a light string over a frictionless pulley. Find the acceleration and the tension. (g = 9.8 m/s^2)",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        False,
    ),
    (
        "In an Atwood machine, m1 = 2 kg and m2 = 3 kg. Find the acceleration.",
        {"scene": "atwood", "values": {"mass1": "2 kg", "mass2": "3 kg"}},
        True,
    ),
    (
        "A 4 kg mass and a 6 kg mass are tied to the ends of a rope passing over a frictionless pulley. Find the acceleration of the system.",
        {"scene": "atwood", "values": {"mass1": "4 kg", "mass2": "6 kg"}},
        True,
    ),
    (
        "A 5 kg mass and a 3 kg mass hang over a light pulley. The system is released from rest. How fast is the 5 kg mass moving after 2 s?",
        {"scene": "atwood", "values": {"mass1": "5 kg", "mass2": "3 kg"}},
        False,
    ),
    (
        "A 2 kg ball moving at 4 m/s collides with a 3 kg ball at rest. The balls stick together. Find their final velocity.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "4 m/s", "mass2": "3 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "A 0.2 kg ball travelling at 5 m/s makes an elastic collision with a stationary 0.3 kg ball.",
        {
            "scene": "collision",
            "values": {"mass1": "0.2 kg", "speed1": "5 m/s", "mass2": "0.3 kg"},
            "elastic": True,
        },
        True,
    ),
    (
        "A 1000 kg car traveling at 15 m/s crashes into the back of a stationary 2000 kg truck. The vehicles stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "1000 kg", "speed1": "15 m/s", "mass2": "2000 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "A 60 g ball with a velocity of 8 m/s hits a 120 g ball at rest in a perfectly inelastic collision.",
        {
            "scene": "collision",
            "values": {"mass1": "60 g", "speed1": "8 m/s", "mass2": "120 g"},
            "sticks": True,
        },
        True,
    ),
    (
        "A simple pendulum has a length of 2 m. Find its period.",
        {"scene": "pendulum", "values": {"length": "2 m"}},
        True,
    ),
    (
        "What is the period of a 0.5 m long pendulum on Earth?",
        {"scene": "pendulum", "values": {"length": "0.5 m"}},
        True,
    ),
    (
        "A pendulum of length 1.2 m swings with a small amplitude. Calculate its frequency (g = 9.81 m/s^2).",
        {"scene": "pendulum", "values": {"length": "1.2 m"}},
        False,
    ),
    (
        "A light ray passes from air into glass with refractive index 1.5 at an angle of incidence of 30 degrees. Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        True,
    ),
    (
        "Light is incident on water (n = 1.33) at 45 degrees. Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "45°", "index": "1.33"}},
        True,
    ),
    (
        "A ray of light strikes a block of glass (n = 1.52) at an angle of 40 degrees to the normal.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.52"}},
        False,
    ),
    (
        "Light travels from water (n = 1.33) into glass (n = 1.5) at an angle of incidence of 35 degrees.",
        {"scene": "refraction", "values": {"angle": "35°", "index": "1.5", "index_from": "1.33"}},
        False,
    ),
    (
        "An object is placed 30 cm in front of a convex lens of focal length 10 cm. Find the image distance.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "30 cm"}},
        True,
    ),
    (
        "A 4 cm tall object is 20 cm from a converging lens with a focal length of 15 cm. Find the image distance and height.",
        {
            "scene": "lens",
            "values": {
                "focal_length": "15 cm",
                "object_distance": "20 cm",
                "object_height": "4 cm",
            },
        },
        False,
    ),
    (
        "A converging lens has a focal length of 12 cm. An object is placed 36 cm from the lens. Where is the image?",
        {"scene": "lens", "values": {"focal_length": "12 cm", "object_distance": "36 cm"}},
        True,
    ),
    (
        "A satellite orbits the Earth at a height of 500 km. Find its speed.",
        {"scene": "orbit", "values": {"altitude": "500 km"}},
        False,
    ),
    (
        "The International Space Station orbits about 400 km above Earth's surface. What is its orbital speed?",
        {"scene": "orbit", "values": {"altitude": "400 km"}},
        True,
    ),
    (
        "A satellite is in a circular orbit 2000 km above the surface of the Earth. Find its period.",
        {"scene": "orbit", "values": {"altitude": "2000 km"}},
        True,
    ),
    (
        "A 0.5 kg mass on a horizontal frictionless surface is attached to a spring with k = 200 N/m. Find the period.",
        {"scene": "spring", "values": {"spring_constant": "200 N/m", "mass": "0.5 kg"}},
        False,
    ),
    (
        "A mass of 0.4 kg oscillates on a spring of spring constant 160 N/m. Find the period.",
        {"scene": "spring", "values": {"spring_constant": "160 N/m", "mass": "0.4 kg"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at 30 degrees from the top of a 45 m cliff. It lands after 4 s? no: find the time.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        True,
    ),
    (
        "A ball is thrown from the top of a cliff at 15 m/s at 30 degrees above the horizontal. How high is the cliff if it lands after 4 s?",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "30°"}},
        False,
    ),
    (
        "A ball is thrown from the top of a cliff at 15 m/s at 30 degrees above the horizontal. Find the height of the cliff if the ball lands 4 s later.",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "30°"}},
        False,
    ),
    (
        "A ball is thrown down at an angle of 30 degrees at 15 m/s from the top of a 45 m cliff. Find the time to land.",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at 50 degrees and lands on the roof of a 10 m high building. Find the time of flight.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "50°"}},
        False,
    ),
    (
        "A ray of light is incident at 40 degrees to the normal to the plane surface of a glass block (n = 1.5). Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.5"}},
        False,
    ),
    (
        "A ray in air strikes glass (n = 1.5); the refracted ray makes 30 degrees with the normal. Find the angle of incidence.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        False,
    ),
    (
        "Light inside water (n = 1.33) is incident on the surface at 45 degrees to the normal. Find the angle of refraction in air.",
        {"scene": "refraction", "values": {"angle": "45°", "index": "1.33"}},
        False,
    ),
    (
        "A ray of light in glass (n = 1.5) strikes the surface at an angle of incidence of 30 degrees and passes into air. Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        False,
    ),
    (
        "An object is placed 15 cm from a lens of focal length 10 cm. Find the image distance.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "15 cm"}},
        True,
    ),
    (
        "An object is placed 15 cm from a lens of focal length -10 cm. Find the image distance.",
        {"scene": "lens", "values": {"focal_length": "-10 cm", "object_distance": "15 cm"}},
        False,
    ),
    (
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest. They do not stick together. Find the speed of the 1 kg cart if the 2 kg cart moves at 1 m/s afterwards.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        False,
    ),
    (
        "A 2 kg cart moving east at 3 m/s collides with a 1 kg cart moving west at 4 m/s. They stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg", "speed2": "4 m/s"},
            "sticks": True,
        },
        False,
    ),
    (
        "A block is given a speed of 8 m/s up a 30 degree incline with kinetic friction coefficient 0.2. How far up does it slide?",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.2"}},
        False,
    ),
    (
        "A 5 kg block is pushed down a 30 degree incline; the coefficient of kinetic friction is 0.2. Find the acceleration.",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.2", "mass": "5 kg"}},
        True,
    ),
    (
        "A satellite orbits 300 km above Mars. Find its orbital speed.",
        {"scene": "orbit", "values": {"altitude": "300 km"}},
        True,
    ),
    (
        "A satellite orbits at a radius of 7000 km from the centre of the Earth. Find its speed.",
        {"scene": "orbit", "values": {"altitude": "7000 km"}},
        False,
    ),
    (
        "On the Moon (g = 1.6 m/s^2) a ball is thrown at 10 m/s at 45 degrees. Find its range.",
        {"scene": "projectile", "values": {"speed": "10 m/s", "angle": "45°", "g": "1.6 m/s^2"}},
        True,
    ),
    (
        "A 3 kg block on a table is connected over a pulley to a hanging 2 kg mass.",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "2 kg"}},
        False,
    ),
    (
        "A simple pendulum 2 m long swings in a lift accelerating upward at 2 m/s^2. Find its period.",
        {"scene": "pendulum", "values": {"length": "2 m"}},
        False,
    ),
    (
        "A pendulum 1 m long on the Moon (g = 1.6 m/s^2). Find its period.",
        {"scene": "pendulum", "values": {"length": "1 m", "g": "1.6 m/s^2"}},
        True,
    ),
    (
        "A conical pendulum has a string 1.2 m long at 25 degrees to the vertical. Find its period.",
        {"scene": "pendulum", "values": {"length": "1.2 m"}},
        False,
    ),
    (
        "A curve of radius 80 m is banked at 15 degrees. Find the speed at which no friction is needed.",
        {"scene": "banked_curve", "values": {"angle": "15°"}},
        True,
    ),
    (
        "A stone is thrown horizontally from a cliff 45 m high with a speed of 12 m/s. How far from the base does it land?",
        {
            "scene": "projectile",
            "values": {"speed": "12 m/s", "height": "45 m"},
            "horizontal": True,
        },
        True,
    ),
    (
        "A stone is thrown from the top of a 45 m high cliff with a speed of 20 m/s at 30 degrees above the horizontal. Find (a) the time of flight, (b) how far from the base of the cliff it lands, and (c) its speed just before it hits the ground.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        True,
    ),
    (
        "A 5 kg block starts from rest at the top of a 4 m long incline at 35 degrees. The coefficient of kinetic friction is 0.25. Find (a) its acceleration, (b) its speed at the bottom, and (c) the time to reach the bottom.",
        {"scene": "incline", "values": {"angle": "35°", "friction": "0.25", "mass": "5 kg"}},
        True,
    ),
    (
        "Two masses of 3 kg and 5 kg hang on either side of a light frictionless pulley and are released from rest. Find (a) the acceleration, (b) the tension in the string, and (c) the speed of the 5 kg mass after it has fallen 1.2 m.",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        True,
    ),
    (
        "A 0.2 kg ball travelling at 5 m/s makes an elastic collision with a stationary 0.3 kg ball. Find the velocities after.",
        {
            "scene": "collision",
            "values": {"mass1": "0.2 kg", "speed1": "5 m/s", "mass2": "0.3 kg"},
            "elastic": True,
        },
        True,
    ),
    (
        "A 10 g bullet moving at 400 m/s embeds itself in a 2 kg wooden block at rest on a frictionless surface. Find the speed of the block.",
        {
            "scene": "collision",
            "values": {"mass1": "10 g", "speed1": "400 m/s", "mass2": "2 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "A simple pendulum of length 1.5 m with a 0.2 kg bob is pulled aside to 10 degrees from the vertical and released. Find (a) its period, (b) the bob's maximum speed.",
        {"scene": "pendulum", "values": {"length": "1.5 m"}},
        True,
    ),
    (
        "A ray of light strikes a block of glass (n = 1.52) at an angle of 40 degrees to the normal. Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.52"}},
        True,
    ),
    (
        "Light travels from water (n = 1.33) into glass (n = 1.5) at an angle of incidence of 35 degrees. Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "35°", "index": "1.5", "index_from": "1.33"}},
        True,
    ),
    (
        "A satellite moves in a circular orbit 600 km above the Earth's surface. Take the Earth's mass as 5.97 x 10^24 kg and its radius as 6370 km. Find (a) its orbital speed, (b) its orbital period in minutes.",
        {
            "scene": "orbit",
            "values": {
                "altitude": "600 km",
                "planet_mass": "5.97 x 10^24 kg",
                "planet_radius": "6370 km",
            },
        },
        True,
    ),
    (
        "A curve of radius 80 m is banked at 15 degrees. (a) At what speed can a car take the curve with no friction needed?",
        {"scene": "banked_curve", "values": {"angle": "15°"}},
        True,
    ),
]

# (texts, the problem first, as the turn's follow-up resolution gives it; description; drawn)
_FOLLOW_UPS: list[tuple[list[str], dict[str, Any], bool]] = [
    (
        [
            "draw it",
            "what if the speed were 25 m/s?",
            "A ball is kicked at 20 m/s at 30 degrees above the horizontal.",
        ],
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°"}},
        False,
    ),
    (
        ["now with 25 m/s", "A ball is kicked at 20 m/s at 30 degrees above the horizontal."],
        {"scene": "projectile", "values": {"speed": "25 m/s", "angle": "30°"}},
        False,
    ),
    # The follow-up's problem as the turn rewrote it ("now with 25 m/s"), first.
    (
        [
            "A ball is kicked at 25 m/s at 30 degrees above the horizontal. Find its range.",
            "now with 25 m/s",
            "A ball is kicked at 20 m/s at 30 degrees above the horizontal. Find its range.",
        ],
        {"scene": "projectile", "values": {"speed": "25 m/s", "angle": "30°"}},
        True,
    ),
]


@pytest.mark.parametrize(("question", "described", "drawn"), _CASES)
def test_a_described_scene_is_drawn_only_when_the_question_confirms_it(
    question: str, described: dict[str, Any], drawn: bool
) -> None:
    body = json.dumps({"kind": "scene", **described})
    assert bool(described_scene(body, [question])) is drawn


@pytest.mark.parametrize(("texts", "described", "drawn"), _FOLLOW_UPS)
def test_a_follow_up_is_checked_against_the_problem_it_points_to(
    texts: list[str], described: dict[str, Any], drawn: bool
) -> None:
    """Never the newest earlier message with a number in it ("what if it were 25 m/s?"):
    only the problem the turn's follow-up resolution names, first."""
    body = json.dumps({"kind": "scene", **described})
    assert bool(described_scene(body, texts)) is drawn
