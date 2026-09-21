"""Complete literal physics requests may display their existing verified result.

This grammar validates quantities and their roles; it does not solve equations
or discard extra clauses. The block carries the exact intent that was solved.
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.models.schemas.math import MathIntent
from app.models.schemas.physics import PhysicsIntent
from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.services.physics.block import _format_visible_answer
from app.services.physics.extract import _LENGTH_UNIT_PATTERN, _VELOCITY_UNIT_PATTERN
from app.services.solving import VerifiedMathBlock

_NUMBER = r"-?(?:[0-9]{1,12}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})"
_TIME = r"seconds?|s|minutes?|min|milliseconds?|ms|hours?|hr|h"
_MASS = r"kg|mg|g|lbs|lb|oz"
_ACCELERATION = r"m/s\^?2"
_ASK = r"(?:find|calculate|compute|determine|what is) (?:the|its) "
_GRAVITY = re.compile(rf"g\s*=\s*(?P<g>{_NUMBER})(?:\s+m/s\^?2)?", re.IGNORECASE)
_EXTRA_REQUEST = re.compile(
    r"\b(?:hint|air resistance|(?<!stokes )(?<!stokes' )drag|wind|"
    r"convert the answer|convert (?:it|this|that))\b"
    r"|\b(?:and|also|then)\s+(?:solve|calculate|compute|find|convert|explain|show|tell)\b",
    re.IGNORECASE,
)


def _quantity(name: str, unit: str) -> str:
    return rf"(?P<{name}>{_NUMBER})\s*(?P<{name}_unit>{unit})"


_DROP = re.compile(
    r"(?:a|an) (?:ball|object|stone) is "
    r"(?:dropped from(?: a height of)?|in free fall from) "
    + _quantity("h0", _LENGTH_UNIT_PATTERN)
    + r"\. "
    + _ASK
    + r"(?P<quantity>time to (?:the )?ground|velocity|speed|height|acceleration)"
    + rf"(?: after {_quantity('t', _TIME)})?",
    re.IGNORECASE,
)
_PROJECTILE = re.compile(
    r"a projectile is launched at "
    + _quantity("v0", _VELOCITY_UNIT_PATTERN)
    + r" at "
    + _quantity("angle", r"degrees?|deg|°")
    + r"\. "
    + _ASK
    + r"(?P<quantity>range|maximum height)",
    re.IGNORECASE,
)
_FORCE = (
    (
        "force",
        re.compile(
            _ASK
            + r"force on a "
            + _quantity("m", _MASS)
            + r" object with acceleration "
            + _quantity("a", _ACCELERATION),
            re.IGNORECASE,
        ),
    ),
    (
        "acceleration",
        re.compile(
            _ASK
            + r"acceleration of a "
            + _quantity("m", _MASS)
            + r" object under a force of "
            + _quantity("F", "N"),
            re.IGNORECASE,
        ),
    ),
    (
        "mass",
        re.compile(
            _ASK
            + r"mass of an object with force "
            + _quantity("F", "N")
            + r" and acceleration "
            + _quantity("a", _ACCELERATION),
            re.IGNORECASE,
        ),
    ),
)
_ENERGY = (
    (
        "kinetic_energy",
        re.compile(
            _ASK
            + r"kinetic energy of a "
            + _quantity("m", _MASS)
            + r" object moving at "
            + _quantity("v", _VELOCITY_UNIT_PATTERN),
            re.IGNORECASE,
        ),
    ),
    (
        "potential_energy",
        re.compile(
            _ASK
            + r"potential energy of a "
            + _quantity("m", _MASS)
            + r" object at (?:a )?height (?:of )?"
            + _quantity("h", _LENGTH_UNIT_PATTERN),
            re.IGNORECASE,
        ),
    ),
    (
        "work",
        re.compile(
            _ASK
            + r"work done by a force of "
            + _quantity("F", "N")
            + r" over a distance of "
            + _quantity("d", _LENGTH_UNIT_PATTERN),
            re.IGNORECASE,
        ),
    ),
    (
        "power",
        re.compile(
            _ASK
            + r"power of a force of "
            + _quantity("F", "N")
            + r" moving at "
            + _quantity("v", _VELOCITY_UNIT_PATTERN),
            re.IGNORECASE,
        ),
    ),
)
_AVERAGE_SPEED = re.compile(
    _ASK
    + r"average speed for "
    + _quantity("d", _LENGTH_UNIT_PATTERN)
    + r" in "
    + _quantity("t", _TIME),
    re.IGNORECASE,
)
_TRAVEL_AVERAGE_SPEED = re.compile(
    r"(?:a|an|the) [A-Za-z][A-Za-z -]{0,40}? "
    r"(?:travels?|covers?|moves?) "
    + _quantity("d", _LENGTH_UNIT_PATTERN)
    + r" (?:in|over) "
    + _quantity("t", _TIME)
    + r"[.!?]? "
    + _ASK
    + r"average (?:speed|velocity)",
    re.IGNORECASE,
)


def _request(text: str) -> tuple[str, float, bool] | None:
    if len(text) > 1000:
        return None
    request = " ".join(text.split()).replace("\u2212", "-").rstrip(".?")
    if request.lower().startswith("please "):
        request = request[7:]
    body, separator, gravity = request.lower().rpartition(". use ")
    if not separator:
        return request, 9.81, False
    match = _GRAVITY.fullmatch(gravity)
    if match is None:
        return None
    g = float(match["g"])
    if not 0 < g <= 1e6:
        return None
    # Slice the original string so SI unit case is never discarded.
    return request[: len(body)], g, True


def _measures(match: re.Match[str]) -> tuple[dict[str, float], dict[str, str]]:
    groups = match.groupdict()
    params = {
        key[:-5]: float(groups[key[:-5]])
        for key, value in groups.items()
        if key.endswith("_unit") and value is not None
    }
    units = {
        key[:-5]: value
        for key, value in groups.items()
        if key.endswith("_unit") and value is not None
    }
    return params, units


def _expected_intent(text: str) -> MathIntent | PhysicsIntent | None:
    parsed = _request(text)
    if parsed is None:
        return None
    body, g, explicit_g = parsed
    match = _DROP.fullmatch(body)
    if match:
        params, units = _measures(match)
        quantity = match["quantity"].lower()
        op = {
            "height": "position",
            "time to ground": "time_to_ground",
            "time to the ground": "time_to_ground",
        }.get(quantity, quantity)
        if params["h0"] <= 0 or ("t" in params) != (op in {"position", "velocity", "speed"}):
            return None
        if "t" in params and params["t"] <= 0:
            return None
        params.update(g=g, v0=0.0)
        units.update(g="m/s^2", v0="m/s")
        return _intent("kinematics", op, params, units)
    match = _PROJECTILE.fullmatch(body)
    if match:
        params, units = _measures(match)
        if params["v0"] <= 0 or not 0 < params["angle"] < 90:
            return None
        params["g"] = g
        units.update(g="m/s^2", angle="deg")
        op = "range" if match["quantity"].lower() == "range" else "max_height"
        return _intent("projectile", op, params, units)
    for quantity, pattern in _FORCE:
        match = pattern.fullmatch(body)
        if match is None or explicit_g:
            continue
        params, units = _measures(match)
        if "m" in params and params["m"] <= 0:
            return None
        if quantity == "mass" and (params["a"] == 0 or params["F"] / params["a"] <= 0):
            return None
        return _intent("force", "net_force", params, units)
    for op, pattern in _ENERGY:
        match = pattern.fullmatch(body)
        if match is None or (explicit_g and op != "potential_energy"):
            continue
        params, units = _measures(match)
        if ("m" in params and params["m"] <= 0) or ("d" in params and params["d"] < 0):
            return None
        if op == "potential_energy":
            params["g"] = g
            units["g"] = "m/s^2"
        return _intent("energy", op, params, units)
    for pattern in (_AVERAGE_SPEED, _TRAVEL_AVERAGE_SPEED):
        match = pattern.fullmatch(body)
        if match is None or explicit_g:
            continue
        params, _units = _measures(match)
        if not 0 <= params["d"] <= 1e6 or not 0 < params["t"] <= 1e6:
            return None
        from app.services.math.tools.school import extract_average_speed_intent

        intent = extract_average_speed_intent(body)
        if intent is not None and intent.expr == f"{params['d']}/{params['t']}":
            return intent
    if not explicit_g:
        from app.services.math.tools.school import extract_average_speed_intent

        speed_intent = extract_average_speed_intent(body)
        if speed_intent is not None and speed_intent.school_op in {
            "average_speed",
            "speed_formula_speed",
            "speed_formula_distance",
            "speed_formula_time",
        }:
            return speed_intent
    return None


def _intent(
    kind: str, op: str, params: dict[str, float], units: dict[str, str]
) -> PhysicsIntent | None:
    if any(not math.isfinite(value) or abs(value) > 1e6 for value in params.values()):
        return None
    return PhysicsIntent.model_validate(
        {
            "kind": kind,
            "physics_op": op,
            "physics_params": params,
            "physics_units": units,
            "operation": "solve",
        }
    )


def _expected_trajectory_type(intent: PhysicsIntent) -> str:
    """The one ``trajectory_type`` ``solve_physics`` emits for this intent.

    Must stay in lockstep with ``solve_kinematics`` / ``solve_projectile``. This
    guard exists to prove the fence came from that solve rather than from the
    model, so an extra value here would be a hole — and a missing one silently
    drops the whole direct reply, which is the harder failure to notice.
    """
    if intent.kind == "projectile":
        return "parametric"
    if intent.physics_op in ("velocity", "speed"):
        return "velocity_vs_time"
    return "position_vs_time"


def can_direct_physics(
    verified: VerifiedMathBlock, text: str, fences: list[dict[str, Any]]
) -> bool:
    expected = _expected_intent(text)
    intent = verified.physics_intent
    if intent is None:
        return False
    answer = verified.canonical_answer
    # P14 attaches a scene alongside the trajectory graph, so a projectile
    # carries two fences where the rule below expects one. A scene is not a
    # second answer — it is an illustration of the same one, server-owned and
    # never model-written — so it is set aside before the count rather than
    # counted. Without this, adding the scene silently switched every
    # projectile back to the provider path: this returned False, the
    # pre-computed reply was dropped, and nothing anywhere reported it.
    answering = [f for f in fences if f.get("type") not in SIMULATION_SPEC_TYPES]
    if not answer or len(answer) > 800 or len(answering) != 1:
        return False
    if isinstance(intent, PhysicsIntent) and not verified.physics_working:
        return False
    fence = answering[0]
    # The legacy exact grammars remain a useful second check for their closed
    # subset. Every other physics kind is already guarded by deterministic
    # extraction plus a solver-owned canonical fence, so it can return without
    # waiting for a language model as well.
    if expected is None:
        if not isinstance(intent, PhysicsIntent):
            return False
        if _EXTRA_REQUEST.search(text):
            return False
        if fence.get("type") == "answer":
            return fence.get("content") == answer
        if fence.get("type") != "trajectory" or fence.get("expr2") or fence.get("points2"):
            return False
        points = fence.get("points")
        return bool(
            isinstance(points, list)
            and len(points) >= 2
            and all(
                isinstance(point, list)
                and len(point) == 2
                and all(type(value) in {int, float} and math.isfinite(value) for value in point)
                for point in points
            )
        )
    if expected != intent:
        return False
    if not isinstance(expected, PhysicsIntent):
        # The speed-law cross-checks are MathIntents with a scalar answer.
        return fence.get("type") == "answer" and fence.get("content") == answer
    if expected.kind in {"force", "energy"} or expected.physics_op == "acceleration":
        return fence.get("type") == "answer" and fence.get("content") == answer
    if fence.get("type") != "trajectory" or fence.get("expr2") or fence.get("points2"):
        return False
    points = fence.get("points")
    return bool(
        isinstance(points, list)
        and len(points) >= 2
        and all(
            isinstance(point, list)
            and len(point) == 2
            and all(type(value) in {int, float} and math.isfinite(value) for value in point)
            for point in points
        )
        and all(
            type(fence.get(key)) in {int, float} and math.isfinite(fence[key])
            for key in ("x_min", "x_max")
        )
        and fence["x_min"] < fence["x_max"]
        and fence.get("trajectory_type") == _expected_trajectory_type(expected)
    )


_SYMBOLS = {
    "angle": r"\theta",
    "mu": r"\mu",
    "h0": r"h_0",
    "v0": r"v_0",
    "d_obj": "u",
    "focal": "f",
    "delta_temp": r"\Delta T",
    "temp": "T",
    "c_heat": "c",
    "b_field": "B",
    "wire_L": "L",
    "radius_body": "R",
    "inertia": "I",
    "wavelength": r"\lambda",
    "freq": "f",
    "freq2": "f_2",
    "E_out": "E_{out}",
    "E_in": "E_{in}",
    "x1": "x_1",
    "x2": "x_2",
    "m1": "m_1",
    "m2": "m_2",
    "v1": "v_1",
    "v2": "v_2",
    "v_wave": "v",
    "tension": "T",
    "linear_density": r"\mu",
    "sound_power": "P",
    "harmonic": "n",
    "alpha": r"\alpha",
    "latent_heat": "L",
    "heat": "Q",
    "pres1": "P_1",
    "rho": r"\rho",
    "F1": "F_1",
    "A1": "A_1",
    "A2": "A_2",
    "L0": "L_0",
    "capacitance": "C",
    "intensity0": "I_0",
    "proper_time": r"\Delta t_0",
    "proper_length": "L_0",
    "work_function": r"\phi",
    "uncertainty_x": r"\Delta x",
    "quantum_n": "n",
    "temp_env": "T_C",
    "emissivity": r"\epsilon",
    "thermal_conductivity": "k",
    "viscosity": r"\eta",
    "surface_tension": r"\gamma",
    "q1": "q_1",
    "q2": "q_2",
}

_RESULT_SYMBOLS = {
    "position": "h",
    "velocity": "v",
    "time_to_ground": "t",
    "speed": "v",
    "acceleration": "a",
    "range": "R",
    "max_height": "H_{max}",
    "time_of_flight": "t_{flight}",
    "impact_speed": "v_{impact}",
    "launch_angle": r"\theta",
    "net_force": "F",
    "tension": "T",
    "atwood": r"a,\ T",
    "resultant_force": "R",
    "resolve_force": r"F_x,\ F_y",
    "kinetic_energy": "KE",
    "potential_energy": "PE",
    "work": "W",
    "power": "P",
    "mechanical_efficiency": r"\eta",
    "momentum": "p",
    "impulse": "J",
    "final_velocity": "v_f",
    "center_of_mass": "x_{cm}",
    "friction_force": "f",
    "normal_force": "N",
    "incline_acceleration": "a",
    "friction_coefficient": r"\mu",
    "minimum_force": "F_{min}",
    "centripetal_force": "F_c",
    "centripetal_acceleration": "a_c",
    "orbital_period": "T",
    "angular_velocity": r"\omega",
    "spring_force": "F",
    "spring_energy": "E_s",
    "shm_period": "T",
    "pendulum_period": "T",
    "shm_frequency": "f",
    "shm_max_speed": "v_{max}",
    "voltage": "V",
    "current": "I",
    "resistance": "R",
    "electrical_power": "P",
    "series_resistance": "R_s",
    "parallel_resistance": "R_p",
    "charge": "Q",
    "electrical_energy": "E",
    "capacitance": "C",
    "parallel_plate_capacitance": "C",
    "capacitor_energy": "U",
    "rc_time_constant": r"\tau",
    "terminal_voltage": "V_{terminal}",
    "torque": r"\tau",
    "moment_balance": "d_2",
    "suvat_velocity": "v",
    "suvat_distance": "s",
    "suvat_time": "t",
    "suvat_acceleration": "a",
    "wave_speed": "v",
    "wavelength": r"\lambda",
    "wave_frequency": "f",
    "wave_frequency_from_period": "f",
    "wave_period": "T",
    "doppler_frequency": "f'",
    "string_wave_speed": "v",
    "resonance_frequency": "f_n",
    "sound_intensity": "I",
    "beat_frequency": "f_b",
    "image_distance": "v",
    "magnification": "m",
    "refractive_index": "n",
    "critical_angle": r"\theta_c",
    "lens_power": "P",
    "double_slit_fringe_spacing": r"\Delta y",
    "diffraction_central_width": "w",
    "malus_intensity": "I",
    "brewster_angle": r"\theta_B",
    "heat_energy": "Q",
    "ideal_gas_pressure": "P",
    "thermal_efficiency": r"\eta",
    "linear_expansion": r"\Delta L",
    "latent_heat": "Q",
    "first_law_internal_energy": r"\Delta U",
    "carnot_efficiency": r"\eta_C",
    "entropy_change": r"\Delta S",
    "heat_conduction_rate": r"Q/t",
    "gravitational_force": "F",
    "orbital_velocity": "v",
    "escape_velocity": "v_e",
    "surface_gravity": "g",
    "pressure_from_force": "P",
    "pressure_at_depth": "P",
    "upthrust": "F_b",
    "density": r"\rho",
    "continuity_velocity": "v_2",
    "flow_rate": "Q",
    "hydraulic_force": "F_2",
    "bernoulli_pressure": "P_2",
    "mass_flow_rate": r"\dot{m}",
    "torricelli_speed": "v",
    "stokes_drag": "F_d",
    "reynolds_number": "Re",
    "surface_tension": r"\gamma",
    "laplace_pressure": r"\Delta P",
    "moment_of_inertia": "I",
    "angular_momentum": "L",
    "rotational_kinetic_energy": "E_k",
    "magnetic_force_wire": "F",
    "magnetic_force_charge": "F",
    "electric_force": "F_e",
    "magnetic_flux": r"\Phi",
    "electric_field": "E",
    "electric_potential": "V",
    "electric_potential_energy": "U",
    "charged_particle_radius": "r",
    "motional_emf": r"\mathcal{E}",
    "magnetic_field_wire": "B",
    "stress": r"\sigma",
    "strain": r"\varepsilon",
    "youngs_modulus": "E",
    "half_life_remaining": "N",
    "mass_energy": "E",
    "photon_energy": "E",
    "de_broglie_wavelength": r"\lambda",
    "lorentz_factor": r"\gamma",
    "time_dilation": r"\Delta t",
    "length_contraction": "L",
    "photoelectric_kinetic_energy": "K_{max}",
    "uncertainty_momentum": r"\Delta p_{min}",
    "particle_box_energy": "E_n",
    "hydrogen_energy_level": "E_n",
    "compton_shift": r"\Delta\lambda",
    "wien_peak": r"\lambda_{max}",
    "stefan_boltzmann_power": "P",
    "lever_arm": "d",
    "net_torque": r"\tau_{net}",
}

_FORMULA_LAW_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Constant-acceleration equation",
        ("position", "velocity", "time_to_ground", "speed", "acceleration"),
    ),
    (
        "Projectile-motion equation",
        ("range", "max_height", "time_of_flight", "impact_speed", "launch_angle"),
    ),
    ("Newton's second law", ("net_force", "tension", "atwood")),
    ("Vector addition and components", ("resultant_force", "resolve_force")),
    ("Kinetic-energy formula", ("kinetic_energy",)),
    ("Gravitational potential-energy formula", ("potential_energy",)),
    ("Work formula", ("work",)),
    ("Power formula", ("power",)),
    ("Mechanical-efficiency formula", ("mechanical_efficiency",)),
    ("Linear-momentum formula", ("momentum",)),
    ("Impulse-momentum theorem", ("impulse",)),
    ("Conservation of linear momentum", ("final_velocity",)),
    ("Center-of-mass equation", ("center_of_mass",)),
    ("Friction law", ("friction_force", "friction_coefficient", "minimum_force")),
    ("Normal-force balance", ("normal_force",)),
    ("Inclined-plane force equation", ("incline_acceleration",)),
    (
        "Circular-motion equation",
        ("centripetal_force", "centripetal_acceleration", "orbital_period", "angular_velocity"),
    ),
    ("Hooke's law", ("spring_force",)),
    ("Elastic potential-energy formula", ("spring_energy",)),
    (
        "Simple-harmonic-motion equation",
        ("shm_period", "pendulum_period", "shm_frequency", "shm_max_speed"),
    ),
    ("Ohm's law", ("voltage", "current", "resistance")),
    ("Electrical-power formula", ("electrical_power",)),
    ("Series-resistance law", ("series_resistance",)),
    ("Parallel-resistance law", ("parallel_resistance",)),
    ("Charge-current relation", ("charge",)),
    ("Electrical-energy formula", ("electrical_energy",)),
    ("Capacitance formula", ("capacitance",)),
    ("Parallel-plate capacitance", ("parallel_plate_capacitance",)),
    ("Capacitor energy", ("capacitor_energy",)),
    ("RC time constant", ("rc_time_constant",)),
    ("Terminal-voltage equation", ("terminal_voltage",)),
    ("Torque formula", ("torque", "lever_arm")),
    ("Principle of moments", ("moment_balance",)),
    ("Net-torque equation", ("net_torque",)),
    (
        "SUVAT constant-acceleration equation",
        ("suvat_velocity", "suvat_distance", "suvat_time", "suvat_acceleration"),
    ),
    ("Wave equation", ("wave_speed", "wavelength", "wave_frequency")),
    ("Frequency-period relation", ("wave_frequency_from_period", "wave_period")),
    ("Doppler-effect equation", ("doppler_frequency",)),
    ("Wave speed on a string", ("string_wave_speed",)),
    ("Standing-wave resonance", ("resonance_frequency",)),
    ("Spherical-wave intensity", ("sound_intensity",)),
    ("Beat-frequency relation", ("beat_frequency",)),
    ("Thin-lens and mirror equation", ("image_distance",)),
    ("Magnification formula", ("magnification",)),
    ("Snell's law", ("refractive_index",)),
    ("Critical-angle equation", ("critical_angle",)),
    ("Lens-power formula", ("lens_power",)),
    ("Double-slit interference", ("double_slit_fringe_spacing",)),
    ("Single-slit diffraction", ("diffraction_central_width",)),
    ("Malus's law", ("malus_intensity",)),
    ("Brewster's law", ("brewster_angle",)),
    ("Specific-heat equation", ("heat_energy",)),
    ("Ideal-gas law", ("ideal_gas_pressure",)),
    ("Thermal-efficiency formula", ("thermal_efficiency",)),
    ("Linear thermal-expansion law", ("linear_expansion",)),
    ("Latent-heat equation", ("latent_heat",)),
    ("First law of thermodynamics", ("first_law_internal_energy",)),
    ("Carnot-efficiency equation", ("carnot_efficiency",)),
    ("Entropy-change equation", ("entropy_change",)),
    ("Fourier heat-conduction law", ("heat_conduction_rate",)),
    ("Newton's law of gravitation", ("gravitational_force",)),
    ("Orbital-motion equation", ("orbital_velocity", "orbital_period")),
    ("Escape-velocity equation", ("escape_velocity",)),
    ("Surface-gravity equation", ("surface_gravity",)),
    ("Pressure formula", ("pressure_from_force",)),
    ("Hydrostatic-pressure equation", ("pressure_at_depth",)),
    ("Archimedes' principle", ("upthrust",)),
    ("Density formula", ("density",)),
    ("Continuity equation", ("continuity_velocity",)),
    ("Volume-flow-rate formula", ("flow_rate",)),
    ("Pascal's principle", ("hydraulic_force",)),
    ("Bernoulli's equation", ("bernoulli_pressure",)),
    ("Mass-flow-rate equation", ("mass_flow_rate",)),
    ("Torricelli's law", ("torricelli_speed",)),
    ("Stokes' drag law", ("stokes_drag",)),
    ("Reynolds-number equation", ("reynolds_number",)),
    ("Surface-tension definition", ("surface_tension",)),
    ("Young-Laplace equation", ("laplace_pressure",)),
    ("Moment-of-inertia formula", ("moment_of_inertia",)),
    ("Angular-momentum formula", ("angular_momentum",)),
    ("Rotational kinetic-energy formula", ("rotational_kinetic_energy",)),
    ("Magnetic force on a wire", ("magnetic_force_wire",)),
    ("Lorentz magnetic-force law", ("magnetic_force_charge",)),
    ("Coulomb's law", ("electric_force",)),
    ("Magnetic-flux formula", ("magnetic_flux",)),
    ("Electric field of a point charge", ("electric_field",)),
    ("Electric potential of a point charge", ("electric_potential",)),
    ("Electric potential-energy equation", ("electric_potential_energy",)),
    ("Charged-particle magnetic radius", ("charged_particle_radius",)),
    ("Motional-emf equation", ("motional_emf",)),
    ("Magnetic field of a straight wire", ("magnetic_field_wire",)),
    ("Stress formula", ("stress",)),
    ("Strain formula", ("strain",)),
    ("Young's modulus formula", ("youngs_modulus",)),
    ("Radioactive-decay law", ("half_life_remaining",)),
    ("Mass-energy equivalence", ("mass_energy",)),
    ("Photon-energy relation", ("photon_energy",)),
    ("de Broglie relation", ("de_broglie_wavelength",)),
    ("Lorentz-factor equation", ("lorentz_factor",)),
    ("Relativistic time dilation", ("time_dilation",)),
    ("Relativistic length contraction", ("length_contraction",)),
    ("Photoelectric equation", ("photoelectric_kinetic_energy",)),
    ("Heisenberg uncertainty principle", ("uncertainty_momentum",)),
    ("Infinite-square-well energy", ("particle_box_energy",)),
    ("Hydrogen energy-level equation", ("hydrogen_energy_level",)),
    ("Compton-scattering equation", ("compton_shift",)),
    ("Wien's displacement law", ("wien_peak",)),
    ("Stefan-Boltzmann law", ("stefan_boltzmann_power",)),
)

_FORMULA_LAW_NAMES = {
    operation: name for name, operations in _FORMULA_LAW_GROUPS for operation in operations
}

_BASE_FORMULAS = {
    "net_force": r"F = ma",
    "voltage": r"V = IR",
    "current": r"V = IR",
    "resistance": r"V = IR",
    "electrical_power": r"P = VI",
    "parallel_plate_capacitance": r"C = \frac{\epsilon_0A}{d}",
    "capacitor_energy": r"U = \frac{1}{2}CV^2",
    "rc_time_constant": r"\tau = RC",
    "mechanical_efficiency": r"\eta = \frac{E_{out}}{E_{in}}",
    "center_of_mass": r"x_{cm} = \frac{m_1x_1 + m_2x_2}{m_1 + m_2}",
    "torque": r"\tau = Fd\sin(\theta)",
    "lever_arm": r"\tau = Fd\sin(\theta)",
    "moment_balance": r"F_1d_1 = F_2d_2",
    "suvat_velocity": r"v = u + at",
    "suvat_time": r"v = u + at",
    "suvat_acceleration": r"v = u + at",
    "suvat_distance": r"s = ut + \frac{1}{2}at^2",
    "wave_speed": r"v = f\lambda",
    "wavelength": r"v = f\lambda",
    "wave_frequency": r"v = f\lambda",
    "wave_frequency_from_period": r"f = \frac{1}{T}",
    "wave_period": r"f = \frac{1}{T}",
    "string_wave_speed": r"v = \sqrt{\frac{T}{\mu}}",
    "resonance_frequency": r"f_n = \frac{nv}{kL}",
    "sound_intensity": r"I = \frac{P}{4\pi r^2}",
    "beat_frequency": r"f_b = \lvert f_1 - f_2 \rvert",
    "lens_power": r"P = \frac{1}{f}",
    "double_slit_fringe_spacing": r"\Delta y = \frac{\lambda L}{d}",
    "diffraction_central_width": r"w = \frac{2\lambda L}{a}",
    "malus_intensity": r"I = I_0\cos^2\theta",
    "brewster_angle": r"\tan\theta_B = \frac{n_2}{n_1}",
    "image_distance": r"\frac{1}{f} = \frac{1}{u} + \frac{1}{v}",
    "ideal_gas_pressure": r"PV = nRT",
    "linear_expansion": r"\Delta L = \alpha L_0\Delta T",
    "latent_heat": r"Q = mL",
    "first_law_internal_energy": r"\Delta U = Q - W",
    "carnot_efficiency": r"\eta_C = 1 - \frac{T_C}{T_H}",
    "entropy_change": r"\Delta S = \frac{Q_{rev}}{T}",
    "heat_conduction_rate": r"\frac{Q}{t} = kA\frac{\Delta T}{L}",
    "pressure_from_force": r"P = \frac{F}{A}",
    "electric_force": r"F_e = k_e \frac{\lvert q_1q_2\rvert}{r^2}",
    "density": r"\rho = \frac{m}{V}",
    "continuity_velocity": r"A_1v_1 = A_2v_2",
    "hydraulic_force": r"\frac{F_1}{A_1} = \frac{F_2}{A_2}",
    "bernoulli_pressure": (r"P_1 + \frac{1}{2}\rho v_1^2 = P_2 + \frac{1}{2}\rho v_2^2"),
    "mass_flow_rate": r"\dot{m} = \rho Av",
    "torricelli_speed": r"v = \sqrt{2gh}",
    "stokes_drag": r"F_d = 6\pi\eta rv",
    "reynolds_number": r"Re = \frac{\rho vL}{\eta}",
    "surface_tension": r"\gamma = \frac{F}{L}",
    "laplace_pressure": r"\Delta P = \frac{k\gamma}{r}",
    "electric_field": r"E = k_e\frac{\lvert Q\rvert}{r^2}",
    "electric_potential": r"V = k_e\frac{Q}{r}",
    "electric_potential_energy": r"U = k_e\frac{q_1q_2}{r}",
    "charged_particle_radius": r"r = \frac{mv}{\lvert q\rvert B}",
    "motional_emf": r"\mathcal{E} = BLv",
    "magnetic_field_wire": r"B = \frac{\mu_0I}{2\pi r}",
    "lorentz_factor": r"\gamma = \frac{1}{\sqrt{1-v^2/c^2}}",
    "time_dilation": r"\Delta t = \gamma\Delta t_0",
    "length_contraction": r"L = \frac{L_0}{\gamma}",
    "photoelectric_kinetic_energy": r"K_{max} = hf - \phi",
    "uncertainty_momentum": r"\Delta p_{min} = \frac{\hbar}{2\Delta x}",
    "particle_box_energy": r"E_n = \frac{n^2h^2}{8mL^2}",
    "hydrogen_energy_level": r"E_n = -\frac{13.6\,\mathrm{eV}}{n^2}",
    "compton_shift": r"\Delta\lambda = \frac{h}{m_ec}(1-\cos\theta)",
    "wien_peak": r"\lambda_{max}T = b",
    "stefan_boltzmann_power": r"P = \epsilon\sigma AT^4",
}


def _display_number(value: float) -> str:
    magnitude = abs(value)
    if magnitude and (magnitude >= 1e6 or magnitude < 1e-4):
        return f"{value:.6g}"
    return str(int(value)) if value.is_integer() else f"{value:g}"


def _result_symbol(intent: PhysicsIntent, params: dict[str, float]) -> str | None:
    """Return the quantity the solver derived, not merely its shared operation."""
    if intent.kind == "force" and intent.physics_op == "net_force":
        # F = ma uses one operation for three rearrangements. The two supplied
        # quantities identify the missing result unambiguously.
        missing = [symbol for symbol in ("F", "m", "a") if symbol not in params]
        if len(missing) == 1:
            return missing[0]
    if intent.kind == "torque" and intent.physics_op == "moment_balance" and "d2" in params:
        return "F_2"
    if intent.physics_op == "final_velocity" and params.get("elastic") == 1.0:
        return r"v_1',\ v_2'"
    return _RESULT_SYMBOLS.get(intent.physics_op or "")


def _formula_rows(intent: PhysicsIntent, formulas: list[str]) -> list[str]:
    """Name the governing law, show its base form, then any rearrangement."""
    operation = intent.physics_op or ""
    name = _FORMULA_LAW_NAMES.get(operation, "Physics formula")
    if operation == "final_velocity":
        if (intent.physics_params or {}).get("elastic") == 1.0:
            return [
                f"{name}:",
                r"$v_1' = \frac{(m_1-m_2)v_1 + 2m_2v_2}{m_1+m_2}$",
                r"$v_2' = \frac{(m_2-m_1)v_2 + 2m_1v_1}{m_1+m_2}$",
            ]
        return [
            f"{name}:",
            r"$m_1v_1 + m_2v_2 = (m_1+m_2)v_f$",
            r"$v_f = \frac{m_1v_1 + m_2v_2}{m_1+m_2}$",
        ]
    base = _BASE_FORMULAS.get(operation)
    if operation == "resonance_frequency":
        # A pipe closed at one end has a 4L fundamental; an open pipe or a
        # string has 2L. Show the actual universal law for the apparatus rather
        # than exposing the solver's internal denominator selector as "k".
        denominator = 4 if (intent.physics_params or {}).get("mode_factor") == 4 else 2
        base = rf"f_n = \frac{{nv}}{{{denominator}L}}"
    if operation == "laplace_pressure":
        numerator = 4 if (intent.physics_params or {}).get("mode_factor") == 4 else 2
        base = rf"\Delta P = \frac{{{numerator}\gamma}}{{r}}"
    rows = [f"{name}:"]
    if base is None:
        rows.extend(f"${formula}$" for formula in formulas)
        return rows

    rows.append(f"${base}$")
    base_lhs = base.split(" = ", 1)[0].strip()
    for formula in formulas:
        formula_lhs = formula.split(" = ", 1)[0].strip()
        if formula.strip() == base.strip():
            continue
        if formula_lhs == base_lhs:
            rows.append("Equivalent form for the given quantities:")
        else:
            rows.append(f"Rearranged for ${formula_lhs}$:")
        rows.append(f"${formula}$")
    return rows


def _equation_layout(
    working: str,
    *,
    result_symbol: str | None,
) -> tuple[list[str], list[str]]:
    """Separate solver-owned equation chains into symbolic and numeric rows."""
    chains = [chain.strip() for chain in working.split(r", \quad ")]
    formulas: list[str] = []
    substitutions: list[str] = []
    for chain in chains:
        parts = chain.split(" = ")
        lhs = result_symbol if len(chains) == 1 and result_symbol else parts[0].strip()
        arrow_rearrangement = len(parts) >= 3 and r"\Rightarrow" in parts[1]
        if arrow_rearrangement:
            formulas.append(f"{lhs} = {parts[2].split(r'\approx', 1)[0].strip()}")
        elif len(parts) >= 2:
            formula_rhs = parts[1].split(r"\approx", 1)[0].strip()
            formulas.append(f"{parts[0].strip()} = {formula_rhs}")
        else:
            formulas.append(chain)

        if len(parts) >= 3:
            substitution_rhs = parts[-1].split(r"\approx", 1)[0].strip()
            substitutions.append(f"{lhs} = {substitution_rhs}")
        else:
            substitutions.append(chain.split(r"\approx", 1)[0].strip())
    return (
        [_format_visible_answer(formula) for formula in formulas],
        [_format_visible_answer(substitution) for substitution in substitutions],
    )


def format_direct_physics_working(verified: VerifiedMathBlock) -> str | None:
    """Five-section worked layout for a solver-verified instant reply.

    This formats the intent and the solver's exact equation chain; it never
    derives a result. The answer remains the canonical answer fence appended
    by the generic direct formatter.
    """
    intent = verified.physics_intent
    working = verified.physics_working
    speed_ops = {
        "average_speed",
        "speed_formula_speed",
        "speed_formula_distance",
        "speed_formula_time",
    }
    if (
        isinstance(intent, MathIntent)
        and intent.school_op in speed_ops
        and intent.unit_from
        and intent.unit_to
    ):
        operation = intent.school_op
        distance = intent.percent_base
        speed = intent.percent_rate
        duration = intent.point_x
        if operation in {"average_speed", "speed_formula_speed"} and (
            distance is None or duration is None
        ):
            operands = (intent.expr or "").split("/")
            if len(operands) == 2:
                try:
                    distance, duration = (float(value) for value in operands)
                except ValueError:
                    return None
        values = [value for value in (distance, speed, duration) if value is not None]
        if not values or not all(math.isfinite(value) for value in values):
            return None
        length_unit = intent.unit_from
        time_unit = intent.unit_to
        if operation in {"average_speed", "speed_formula_speed"}:
            if distance is None or duration is None or distance < 0 or duration <= 0:
                return None
            distance_text = _display_number(distance)
            duration_text = _display_number(duration)
            given = (
                rf"$d = {distance_text}\,\mathrm{{{length_unit}}}$",
                rf"$t = {duration_text}\,\mathrm{{{time_unit}}}$",
            )
            find = "$v$"
            rearrangement: tuple[str, ...] = ()
            substitution = (
                rf"$v = \frac{{{distance_text}\,\mathrm{{{length_unit}}}}}"
                rf"{{{duration_text}\,\mathrm{{{time_unit}}}}}$"
            )
        elif operation == "speed_formula_distance":
            if speed is None or duration is None or speed < 0 or duration < 0:
                return None
            speed_text = _display_number(speed)
            duration_text = _display_number(duration)
            given = (
                rf"$v = {speed_text}\,\mathrm{{{length_unit}/{time_unit}}}$",
                rf"$t = {duration_text}\,\mathrm{{{time_unit}}}$",
            )
            find = "$d$"
            rearrangement = ("Rearranged for $d$:", "$d = vt$")
            substitution = rf"$d = {speed_text} \cdot {duration_text}$"
        else:
            if distance is None or speed is None or distance < 0 or speed <= 0:
                return None
            distance_text = _display_number(distance)
            speed_text = _display_number(speed)
            given = (
                rf"$d = {distance_text}\,\mathrm{{{length_unit}}}$",
                rf"$v = {speed_text}\,\mathrm{{{length_unit}/{time_unit}}}$",
            )
            find = "$t$"
            rearrangement = ("Rearranged for $t$:", r"$t = \frac{d}{v}$")
            substitution = rf"$t = \frac{{{distance_text}}}{{{speed_text}}}$"
        return "\n\n".join(
            (
                "**Given**",
                *given,
                "**Find**",
                find,
                "**Formula**",
                "Speed formula:",
                r"$v = \frac{d}{t}$",
                *rearrangement,
                "**Substitution**",
                substitution,
                "**Answer**",
            )
        )
    if not isinstance(intent, PhysicsIntent) or not working:
        return None

    params = intent.physics_params or {}
    units = intent.physics_units or {}
    given_rows: list[str] = []
    for name, value in params.items():
        if name in {"elastic", "mode_factor"}:
            continue
        symbol = _SYMBOLS.get(name, name)
        if intent.physics_op == "carnot_efficiency" and name == "temp":
            symbol = "T_H"
        if intent.physics_op == "beat_frequency" and name == "freq":
            symbol = "f_1"
        unit = units.get(name)
        suffix = rf"\,\mathrm{{{unit}}}" if unit else ""
        given_rows.append(rf"${symbol} = {_display_number(value)}{suffix}$")

    result_symbol = _result_symbol(intent, params)
    if intent.kind == "kinematics" and intent.physics_op == "speed" and "t" not in params:
        result_symbol = "v_{impact}"
    formulas, substitutions = _equation_layout(working, result_symbol=result_symbol)
    if intent.physics_op == "final_velocity" and {"m1", "m2", "v1", "v2"} <= params.keys():
        m1 = _display_number(params["m1"])
        m2 = _display_number(params["m2"])
        v1 = _display_number(params["v1"])
        v2 = _display_number(params["v2"])
        if params.get("elastic") == 1.0:
            substitutions = [
                rf"v_1' = \frac{{({m1}-{m2})\cdot {v1} + 2\cdot {m2}\cdot {v2}}}"
                rf"{{{m1}+{m2}}}",
                rf"v_2' = \frac{{({m2}-{m1})\cdot {v2} + 2\cdot {m1}\cdot {v1}}}"
                rf"{{{m1}+{m2}}}",
            ]
        else:
            substitutions = [
                rf"v_f = \frac{{{m1}\cdot {v1} + {m2}\cdot {v2}}}{{{m1}+{m2}}}"
            ]
    if intent.kind == "projectile" and intent.physics_op == "max_height":
        needed = {"v0", "angle", "g"}
        if needed <= params.keys():
            h0 = _display_number(params.get("h0", 0.0))
            substitutions = [
                rf"H_{{max}} = {h0} + "
                rf"\frac{{{_display_number(params['v0'])}^2 "
                rf"\sin^2({_display_number(params['angle'])}^\circ)}}"
                rf"{{2 \cdot {_display_number(params['g'])}}}"
            ]
    if (
        " = " not in working
        and intent.kind == "kinematics"
        and intent.physics_op
        in {
            "velocity",
            "speed",
        }
    ):
        if "t" in params:
            substitutions = [
                rf"v = {_display_number(params['v0'])} - "
                rf"{_display_number(params['g'])} \cdot {_display_number(params['t'])}"
            ]
        else:
            substitutions = [
                rf"v = \sqrt{{({_display_number(params['v0'])})^2 + 2 \cdot "
                rf"{_display_number(params['g'])} \cdot {_display_number(params.get('h0', 0.0))}}}"
            ]

    find_symbol = result_symbol or formulas[0].split(" = ", 1)[0]
    rows = ["**Given**", *given_rows, "**Find**", f"${find_symbol}$", "**Formula**"]
    rows.extend(_formula_rows(intent, formulas))
    rows.append("**Substitution**")
    rows.extend(f"${substitution}$" for substitution in substitutions)
    rows.append("**Answer**")
    return "\n\n".join(rows)
