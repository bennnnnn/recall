"""Every case of the feat/physics-scenes reviews, refusals included.

The server draws a described scene only when the question's words confirm the setup: each
value stated and of its part's kind, every other stated quantity one the scene can leave
aside, and each property a word decides (an angle's reference, a direction, which body
moves, the lens, the media's order, the planet, what vibrates) said in a phrasing the server
recognises beside its value. Any other phrasing draws nothing: a refusal is always
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
        "A 0.5 kg mass on a horizontal spring with k = 200 N/m is pulled 3 cm and released.",
        {"scene": "spring", "values": {"spring_constant": "200 N/m", "mass": "0.5 kg"}},
        True,
    ),
    (
        "A pendulum 2 m long has a 0.5 kg bob released from 10 degrees.",
        {"scene": "pendulum", "values": {"length": "2 m"}},
        True,
    ),
    (
        "A 1.2 m string vibrates in its third harmonic.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}, "harmonic": 3},
        True,
    ),
    (
        "A string 1.2 m long carries a standing wave of wavelength 0.7 m.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}},
        False,
    ),
    (
        "A string 1.2 m long carries a standing wave of wavelength 0.8 m.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}, "harmonic": 2},
        False,
    ),
    (
        "A string 1.2 m long carries a standing wave of wavelength 0.8 m.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}},
        True,
    ),
    (
        "A 3 kg ball moving at 5 m/s catches up with a 1 kg ball moving at 2 m/s in the same direction. They stick.",
        {
            "scene": "collision",
            "values": {"mass1": "3 kg", "speed1": "5 m/s", "mass2": "1 kg", "speed2": "2 m/s"},
            "sticks": True,
        },
        True,
    ),
    (
        "A 3 kg ball moving at 5 m/s collides with a 1 kg ball moving at 2 m/s. They stick.",
        {
            "scene": "collision",
            "values": {"mass1": "3 kg", "speed1": "5 m/s", "mass2": "1 kg", "speed2": "2 m/s"},
            "sticks": True,
        },
        False,
    ),
    (
        "Light passes from glass (n = 1.5) into air at 30 degrees of incidence.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        False,
    ),
    (
        "Light passes from water into glass (n = 1.5) at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.5"}},
        False,
    ),
    (
        "Light strikes a glass surface (n = 1.5) at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.5"}},
        False,
    ),
    (
        "The angle between the ray and the surface is 30 degrees; the glass has n = 1.5.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        False,
    ),
    (
        "A ball is kicked at 20 m/s at 35 degrees. Find the vertical component of its velocity.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "35°"}},
        True,
    ),
    (
        "A ball is thrown at an angle to the vertical of 60 degrees at 20 m/s.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "60°"}},
        False,
    ),
    (
        "Masses of 2 kg and 4 kg hang over the 2 kg pulley. Find the acceleration.",
        {"scene": "atwood", "values": {"mass1": "2 kg", "mass2": "4 kg"}},
        False,
    ),
    (
        "A ball is thrown at 15 m/s from a 20 m high table. Find the range.",
        {
            "scene": "projectile",
            "values": {"speed": "15 m/s", "height": "20 m"},
            "horizontal": True,
        },
        False,
    ),
    (
        "A ball is launched horizontally at 15 m/s from a 20 m high table. Find the range.",
        {
            "scene": "projectile",
            "values": {"speed": "15 m/s", "height": "20 m"},
            "horizontal": True,
        },
        True,
    ),
    (
        "A spring (k = 100 N/m) is compressed 0.2 m and launches a 0.5 kg ball.",
        {"scene": "spring", "values": {"spring_constant": "100 N/m", "mass": "0.5 kg"}},
        False,
    ),
    (
        "A projectile is fired at 30 m/s at 40 degrees. The target is at an angle of 10 degrees.",
        {"scene": "projectile", "values": {"speed": "30 m/s", "angle": "40°"}},
        False,
    ),
    (
        "A 3 kg ball at 4 m/s hits a 2 kg ball at rest and sticks. Then the 3 kg ball and the 2 kg ball move together.",
        {
            "scene": "collision",
            "values": {"mass1": "3 kg", "speed1": "4 m/s", "mass2": "2 kg"},
            "sticks": True,
        },
        True,
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
        "A pendulum 2 m long swings. A second pendulum is 0.5 m long.",
        {"scene": "pendulum", "values": {"length": "2 m"}},
        False,
    ),
    (
        "A string 1.2 m long is fixed at both ends. Find the first three harmonics' frequencies when the wave speed is 120 m/s.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}, "harmonic": 3},
        False,
    ),
    (
        "Question 3: A 5 kg block slides down a 35 degree incline; the coefficient of kinetic friction is 0.25. Give answers to 2 significant figures.",
        {"scene": "incline", "values": {"angle": "35°", "friction": "0.25", "mass": "5 kg"}},
        True,
    ),
    (
        "A ray passes from air (n = 1.00) into glass (n = 1.50) at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.50"}},
        True,
    ),
    (
        "Masses of 2 kg and 4 kg hang from a string over the 2 kg pulley, a uniform disk. Find the acceleration.",
        {"scene": "atwood", "values": {"mass1": "2 kg", "mass2": "4 kg"}},
        False,
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
        "A 0.5 kg ball moving at 4 m/s collides elastically with a stationary 1.5 kg ball.",
        {
            "scene": "collision",
            "values": {"mass1": "0.5 kg", "speed1": "4 m/s", "mass2": "1.5 kg"},
            "elastic": True,
        },
        True,
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
        "A 1500 kg car travelling at 20 m/s rear-ends a 1000 kg car. The cars lock together.",
        {
            "scene": "collision",
            "values": {"mass1": "1500 kg", "speed1": "20 m/s", "mass2": "1000 kg"},
            "sticks": True,
        },
        False,
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
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest. They stick together. Find their speed.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        True,
    ),
    (
        "A ball is thrown at 20 m/s at 30 degrees from a 45 m cliff. It lands 2.5 s later.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at 30 degrees below the horizontal from a 45 m cliff.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        False,
    ),
    (
        "A stone is thrown from the top of a 45 m high cliff with a speed of 20 m/s at 30 degrees above the horizontal. Take g = 10 m/s^2.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        True,
    ),
    (
        "A stone is thrown from the top of a 45 m high cliff with a speed of 20 m/s at 30 degrees above the horizontal.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°", "height": "45 m"}},
        True,
    ),
    (
        "A 5 kg block starts from rest at the top of a 4 m long incline at 35 degrees. The coefficient of kinetic friction is 0.25.",
        {"scene": "incline", "values": {"angle": "35 degrees", "friction": "0.25", "mass": "5 kg"}},
        True,
    ),
    (
        "A 5 kg block starts from rest at the top of a 4 m long incline at 35 degrees. The coefficient of kinetic friction is 0.25.",
        {"scene": "incline", "values": {"angle": "35°", "friction": "0.25", "mass": "5 kg"}},
        True,
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
        "A 1 kg ball moving at 2 m/s is struck from behind by a 3 kg ball moving at 5 m/s; the collision is elastic.",
        {
            "scene": "collision",
            "values": {"mass1": "3 kg", "speed1": "5 m/s", "mass2": "1 kg", "speed2": "2 m/s"},
            "elastic": True,
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
        "A 2 kg cart moving at 3 m/s hits a 1 kg cart at rest. They stick together.",
        {
            "scene": "collision",
            "values": {"mass1": "2 kg", "speed1": "3 m/s", "mass2": "1 kg"},
            "sticks": True,
        },
        True,
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
        "An object 2 cm tall is placed 15 cm in front of a converging lens of focal length 10 cm.",
        {
            "scene": "lens",
            "values": {
                "focal_length": "10 cm",
                "object_distance": "15 cm",
                "object_height": "2 cm",
            },
        },
        True,
    ),
    (
        "An object 2 cm tall is placed 5 cm in front of a converging lens of focal length 10 cm.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "5 cm"}},
        False,
    ),
    (
        "A curve is banked at 15 degrees; the angle between the car's path and north is 30 degrees.",
        {"scene": "banked_curve", "values": {"angle": "15°"}},
        False,
    ),
    (
        "A curve of radius 80 m is banked at 15 degrees. A 1200 kg car takes it at 20 m/s.",
        {"scene": "banked_curve", "values": {"angle": "15°"}},
        True,
    ),
    (
        "A string 1.2 m long vibrates; each oscillation takes 0.01 seconds. Sketch it.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}, "harmonic": 2},
        False,
    ),
    (
        "A string 1.2 m long is fixed at both ends; the wave speed is 120 m/s. Find the frequency of the second harmonic in seconds^-1.",
        {"scene": "standing_wave", "values": {"length": "1.2 m"}, "harmonic": 2},
        True,
    ),
    (
        "A 0.5 kg mass hangs on a spring with k = 200 N/m. It is pulled down 3 cm and released. Find the period. Give the answer in seconds.",
        {"scene": "spring", "values": {"spring_constant": "200 N/m", "mass": "0.5 kg"}},
        False,
    ),
    (
        "A satellite orbits 100 km above the Moon's surface. Find its orbital speed.",
        {"scene": "orbit", "values": {"altitude": "100 km"}},
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
        "An object is placed 15 cm in front of a diverging lens of focal length 10 cm. Find the image position.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "15 cm"}},
        False,
    ),
    (
        "Light travels from glass (n = 1.5) into water (n = 1.33) at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.33", "index_from": "1.5"}},
        True,
    ),
    (
        "Light travels from glass (n = 1.5) into water (n = 1.33) at an angle of incidence of 40 degrees.",
        {"scene": "refraction", "values": {"angle": "40°", "index": "1.5", "index_from": "1.33"}},
        False,
    ),
    (
        "A ball is launched horizontally at 15 m/s from a 20 m high table. Find the range.",
        {"scene": "projectile", "values": {"speed": "15 m/s", "angle": "0°", "height": "20 m"}},
        False,
    ),
    (
        "Two masses of 3 kg and 5 kg hang on either side of a light frictionless pulley. Find the acceleration and the speed of the 5 kg mass after it has fallen 1.2 m.",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        True,
    ),
    (
        "Masses of 2 kg and 4 kg hang over a pulley with moment of inertia 0.01 kg m^2 and radius 0.1 m. Find the acceleration.",
        {"scene": "atwood", "values": {"mass1": "2 kg", "mass2": "4 kg"}},
        False,
    ),
    (
        "A block rests on a 20 degree incline; the coefficient of static friction is 0.5. Does it slide?",
        {"scene": "incline", "values": {"angle": "20°", "friction": "0.5"}},
        False,
    ),
    (
        "A 5 kg block is pushed up a 25 degree incline by a horizontal force of 60 N. The coefficient of kinetic friction is 0.3. Find its acceleration.",
        {"scene": "incline", "values": {"angle": "25°", "friction": "0.3", "mass": "5 kg"}},
        False,
    ),
    (
        "A ball is thrown at 20 m/s at 60 degrees to the vertical. Find its range.",
        {"scene": "projectile", "values": {"speed": "20 m/s", "angle": "60°"}},
        False,
    ),
    (
        "A 500 kg satellite orbits 600 km above the Earth's surface. Find its orbital speed.",
        {"scene": "orbit", "values": {"altitude": "600 km"}},
        True,
    ),
    (
        "A ray of light strikes a glass surface (n = 1.5) making an angle of 30 degrees with the surface. Find the angle of refraction.",
        {"scene": "refraction", "values": {"angle": "30°", "index": "1.5"}},
        False,
    ),
    (
        "A 0.3 kg ball on a 1.2 m string moves in a horizontal circle so that the string makes 25 degrees with the vertical (a conical pendulum). Find the tension.",
        {"scene": "pendulum", "values": {"length": "1.2 m"}},
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
        "A 4 kg block on a 30 degree incline is connected by a light string over a frictionless pulley at the top of the incline to a hanging 6 kg mass. The coefficient of kinetic friction between the block and the incline is 0.15. Find the acceleration.",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.15", "mass": "4 kg"}},
        False,
    ),
    (
        "A block is given a speed of 8 m/s up a 30 degree incline. The coefficient of kinetic friction is 0.2. How far up does it slide?",
        {"scene": "incline", "values": {"angle": "30°", "friction": "0.2"}},
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
        False,
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
        True,
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
        True,
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
        True,
    ),
    (
        "A 2 kg block slides down a rough plane inclined at 25 degrees (coefficient of friction 0.3). Find the acceleration.",
        {"scene": "incline", "values": {"angle": "25°", "friction": "0.3", "mass": "2 kg"}},
        True,
    ),
    (
        "Two masses, 3 kg and 5 kg, are connected by a light string over a frictionless pulley. Find the acceleration and the tension. (g = 9.8 m/s^2)",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        True,
    ),
    (
        "An Atwood machine has masses of 3 kg and 5 kg. The system is released from rest. How far does the 5 kg mass fall in 2 s?",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        True,
    ),
    (
        "A 3 kg mass and a 5 kg mass hang from the ends of a string over a pulley. Find the acceleration of the masses.",
        {"scene": "atwood", "values": {"mass1": "3 kg", "mass2": "5 kg"}},
        True,
    ),
    (
        "A simple pendulum is 1.5 m long. Find its period. (g = 9.81 m/s^2)",
        {"scene": "pendulum", "values": {"length": "1.5 m"}},
        True,
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
        True,
    ),
    (
        "A ray of light travels from air into water (n = 1.33) at an angle of incidence of 35 degrees.",
        {"scene": "refraction", "values": {"angle": "35°", "index": "1.33"}},
        True,
    ),
    (
        "An object is placed 30 cm from a converging lens of focal length 10 cm. Find the image distance.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "30 cm"}},
        True,
    ),
    (
        "An object is placed 30 cm from a lens of focal length 10 cm. Find the image distance.",
        {"scene": "lens", "values": {"focal_length": "10 cm", "object_distance": "30 cm"}},
        False,
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
        True,
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
            "A ball is kicked at 25 m/s at 30 degrees above the horizontal.",
            "now with 25 m/s",
            "A ball is kicked at 20 m/s at 30 degrees above the horizontal.",
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
