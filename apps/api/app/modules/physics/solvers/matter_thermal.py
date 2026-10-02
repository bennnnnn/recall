"""Optics, thermal physics, fluids, and materials solvers."""

from __future__ import annotations

import math

from app.models.schemas.physics import (
    PhysicsIntent,
    SimulationVector,
)
from app.modules.physics.display import plain_number
from app.modules.physics.solvers.common import (
    _GAS_CONSTANT,
    _SPEED_OF_LIGHT,
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
)
from app.modules.physics.solvers.mechanics import _free_body_scene
from app.services.solving import SolveServiceError


def solve_optics(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "lens_power":
        if p["focal"] == 0:
            raise SolveServiceError("lens focal length cannot be zero")
        value = 1 / p["focal"]
        return PhysicsResult(
            answer=(
                rf"P = \frac{{1}}{{f}} = \frac{{1}}{{{p['focal']:g}}} "
                rf"\approx {value:.4g} \text{{ D}}"
            ),
            formulas=(r"P = \frac{1}{f}",),
            substitutions=(rf"P = \frac{{1}}{{{p['focal']:g}}}",),
            quantities=(QuantityResult("", value, "D"),),
        )

    if op == "double_slit_fringe_spacing":
        if p["wavelength"] <= 0 or p["L"] <= 0 or p["d"] <= 0:
            raise SolveServiceError("double-slit spacing needs positive wavelength and distances")
        value = p["wavelength"] * p["L"] / p["d"]
        return PhysicsResult(
            answer=(
                rf"\Delta y = \frac{{\lambda L}}{{d}} = "
                rf"\frac{{{p['wavelength']:g} \cdot {p['L']:g}}}{{{p['d']:g}}} "
                rf"\approx {value:.4g} \text{{ m}}"
            ),
            formulas=(r"\Delta y = \frac{\lambda L}{d}",),
            substitutions=(
                rf"\Delta y = \frac{{{p['wavelength']:g} \cdot {p['L']:g}}}{{{p['d']:g}}}",
            ),
            quantities=(QuantityResult("", value, "m"),),
        )

    if op == "diffraction_central_width":
        if p["wavelength"] <= 0 or p["L"] <= 0 or p["d"] <= 0:
            raise SolveServiceError("diffraction width needs positive wavelength and distances")
        value = 2 * p["wavelength"] * p["L"] / p["d"]
        return PhysicsResult(
            answer=(
                rf"w = \frac{{2\lambda L}}{{a}} = "
                rf"\frac{{2 \cdot {p['wavelength']:g} \cdot {p['L']:g}}}{{{p['d']:g}}} "
                rf"\approx {value:.4g} \text{{ m}}"
            ),
            formulas=(r"w = \frac{2\lambda L}{a}",),
            substitutions=(
                rf"w = \frac{{2 \cdot {p['wavelength']:g} \cdot {p['L']:g}}}{{{p['d']:g}}}",
            ),
            quantities=(QuantityResult("", value, "m"),),
        )

    if op == "malus_intensity":
        value = p["intensity0"] * math.cos(p["angle"]) ** 2
        return PhysicsResult(
            answer=(
                rf"I = I_0\cos^2\theta = {p['intensity0']:g} \cdot "
                rf"\cos^2({math.degrees(p['angle']):g}^\circ) "
                rf"\approx {value:.4g} \text{{ W/m}}^2"
            ),
            formulas=(r"I = I_0\cos^2\theta",),
            substitutions=(
                rf"I = {p['intensity0']:g} \cdot \cos^2({math.degrees(p['angle']):g}^\circ)",
            ),
            quantities=(QuantityResult("", value, "W/m^2"),),
        )

    if op == "brewster_angle":
        if p["n1"] <= 0 or p["n2"] <= 0:
            raise SolveServiceError("refractive indexes must be positive")
        value = math.degrees(math.atan(p["n2"] / p["n1"]))
        return PhysicsResult(
            answer=(
                rf"\tan\theta_B = \frac{{n_2}}{{n_1}} \Rightarrow "
                rf"\theta_B = \tan^{{-1}}\!\left(\frac{{{p['n2']:g}}}{{{p['n1']:g}}}\right) "
                rf"\approx {value:.4g}^\circ"
            ),
            formulas=(r"\theta_B = \tan^{-1}\!\left(\frac{n_2}{n_1}\right)",),
            substitutions=(
                rf"\theta_B = \tan^{{-1}}\!\left(\frac{{{p['n2']:g}}}{{{p['n1']:g}}}\right)",
            ),
            quantities=(QuantityResult("", value, "deg"),),
        )

    if op == "critical_angle":
        n = p["n1"]
        if n <= 1:
            raise SolveServiceError("total internal reflection needs an index above 1")
        theta_c = math.degrees(math.asin(1 / n))
        return PhysicsResult(
            answer=(
                rf"\theta_c = \arcsin\!\left(\frac{{1}}{{n}}\right) = "
                rf"\arcsin\!\left(\frac{{1}}{{{n:g}}}\right) \approx {theta_c:.2f}^\circ"
            ),
            formulas=(r"\theta_c = \arcsin\!\left(\frac{1}{n}\right)",),
            substitutions=(rf"\theta_c = \arcsin\!\left(\frac{{1}}{{{n:g}}}\right)",),
            quantities=(QuantityResult("", theta_c, "deg"),),
        )

    if op == "refractive_index":
        if "v_wave" in p:
            if p["v_wave"] <= 0:
                raise SolveServiceError("light speed in a medium must be positive")
            n = _SPEED_OF_LIGHT / p["v_wave"]
            return PhysicsResult(
                answer=(
                    rf"n = \frac{{c}}{{v}} = \frac{{{_SPEED_OF_LIGHT:.0f}}}"
                    rf"{{{p['v_wave']:g}}} \approx {n:.3g}"
                ),
                formulas=(r"n = \frac{c}{v}",),
                substitutions=(rf"n = \frac{{{_SPEED_OF_LIGHT:.0f}}}{{{p['v_wave']:g}}}",),
                quantities=(QuantityResult("", n, ""),),
            )
        t1, t2 = p["angle"], p["angle2"]
        if math.sin(t2) == 0:
            raise SolveServiceError("the refracted angle cannot be zero")
        n = math.sin(t1) / math.sin(t2)
        return PhysicsResult(
            answer=(
                rf"n = \frac{{\sin\theta_1}}{{\sin\theta_2}} = "
                rf"\frac{{\sin({math.degrees(t1):.1f}^\circ)}}"
                rf"{{\sin({math.degrees(t2):.1f}^\circ)}} \approx {n:.2f}"
            ),
            formulas=(r"n = \frac{\sin\theta_1}{\sin\theta_2}",),
            substitutions=(
                rf"n = \frac{{\sin({math.degrees(t1):.1f}^\circ)}}{{\sin({math.degrees(t2):.1f}"
                rf"^\circ)}}",
            ),
            quantities=(QuantityResult("", n, ""),),
        )

    if op == "magnification":
        if p["h_obj"] == 0:
            raise SolveServiceError("the object height cannot be zero")
        m_val = p["h_img"] / p["h_obj"]
        return PhysicsResult(
            answer=(
                rf"m = \frac{{h_i}}{{h_o}} = \frac{{{p['h_img']:g}}}{{{p['h_obj']:g}}} "
                rf"\approx {m_val:.2f}"
            ),
            formulas=(r"m = \frac{h_i}{h_o}",),
            substitutions=(rf"m = \frac{{{p['h_img']:g}}}{{{p['h_obj']:g}}}",),
            quantities=(QuantityResult("", m_val, ""),),
        )

    if op == "image_distance":
        focal, obj = p["focal"], p["d_obj"]
        if focal <= 0 or obj <= 0:
            raise SolveServiceError("only a converging lens with a real object is solved here")
        if obj <= focal:
            # Inside the focal length the image is virtual, and the sign that
            # says so is exactly what the conventions disagree about.
            raise SolveServiceError("an object inside the focal length forms a virtual image")
        img = 1 / (1 / focal - 1 / obj)
        return PhysicsResult(
            answer=(
                rf"\frac{{1}}{{f}} = \frac{{1}}{{u}} + \frac{{1}}{{v}} \Rightarrow v = "
                rf"\frac{{uf}}{{u - f}} = \frac{{{obj:g} \cdot {focal:g}}}"
                rf"{{{obj:g} - {focal:g}}} \approx {img:.4g} \text{{ m}}"
            ),
            formulas=(r"v = \frac{uf}{u - f}",),
            substitutions=(rf"v = \frac{{{obj:g} \cdot {focal:g}}}{{{obj:g} - {focal:g}}}",),
            quantities=(QuantityResult("", img, "m"),),
        )

    raise SolveServiceError(f"unsupported optics op: {op}")


def _temperature_change(intent: PhysicsIntent, p: dict[str, float]) -> tuple[float, str | None]:
    """ΔT in kelvin, and the row that shows it when two readings were given."""
    if "temp_initial" not in p or "temp_final" not in p:
        return p["delta_temp"], None
    change = p["temp_final"] - p["temp_initial"]
    raw = intent.physics_params or {}
    units = intent.physics_units or {}
    same_scale = units.get("temp_initial") == units.get("temp_final")
    first = raw["temp_initial"] if same_scale else p["temp_initial"]
    second = raw["temp_final"] if same_scale else p["temp_final"]
    return change, rf"\Delta T = T_2 - T_1 = {second:g} - {first:g} = {change:g}"


def _heat_energy(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    """Q = mcΔT. Cooling releases heat: the answer is its size, marked released."""
    change, change_row = _temperature_change(intent, p)
    q_val = p["m"] * p["c_heat"] * change
    plugged = rf"{p['m']:g} \cdot {p['c_heat']:g} \cdot {_latex_num(change)}"
    rows = (change_row,) if change_row else ()
    return PhysicsResult(
        answer=rf"Q = mc\Delta T = {plugged} \approx {q_val:.2f} \text{{ J}}",
        formulas=(*rows, r"Q = mc\Delta T"),
        substitutions=(rf"Q = {plugged}",),
        quantities=(QuantityResult("", abs(q_val), "J", detail="released" if q_val < 0 else None),),
    )


def solve_thermal(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "carnot_efficiency":
        hot, cold = p["temp"], p["temp_env"]
        if hot <= 0 or cold < 0 or cold >= hot:
            raise SolveServiceError("Carnot efficiency needs 0 <= T_c < T_h in kelvin")
        value = 1 - cold / hot
        return PhysicsResult(
            answer=(
                rf"\eta_C = 1 - \frac{{T_C}}{{T_H}} = 1 - "
                rf"\frac{{{cold:g}}}{{{hot:g}}} \approx {value:.4g} "
                rf"({value * 100:.4g}\%)"
            ),
            formulas=(r"\eta_C = 1 - \frac{T_C}{T_H}",),
            substitutions=(rf"\eta_C = 1 - \frac{{{cold:g}}}{{{hot:g}}}",),
            quantities=(
                QuantityResult(
                    "",
                    value,
                    "",
                    detail=f"{value * 100:.4g}%",
                ),
            ),
        )

    if op == "entropy_change":
        if p["temp"] <= 0:
            raise SolveServiceError("entropy change needs a positive absolute temperature")
        value = p["heat"] / p["temp"]
        return PhysicsResult(
            answer=(
                rf"\Delta S = \frac{{Q_{{rev}}}}{{T}} = "
                rf"\frac{{{p['heat']:g}}}{{{p['temp']:g}}} "
                rf"\approx {value:.4g} \text{{ J/K}}"
            ),
            formulas=(r"\Delta S = \frac{Q_{rev}}{T}",),
            substitutions=(rf"\Delta S = \frac{{{p['heat']:g}}}{{{p['temp']:g}}}",),
            quantities=(QuantityResult("", value, "J/K"),),
        )

    if op == "heat_conduction_rate":
        if p["thermal_conductivity"] < 0 or p["area"] <= 0 or p["L"] <= 0:
            raise SolveServiceError("heat conduction needs positive area and thickness")
        value = p["thermal_conductivity"] * p["area"] * abs(p["delta_temp"]) / p["L"]
        return PhysicsResult(
            answer=(
                rf"\frac{{Q}}{{t}} = kA\frac{{\Delta T}}{{L}} = "
                rf"{p['thermal_conductivity']:g} \cdot {p['area']:g} \cdot "
                rf"\frac{{{abs(p['delta_temp']):g}}}{{{p['L']:g}}} "
                rf"\approx {value:.4g} \text{{ W}}"
            ),
            formulas=(r"\frac{Q}{t} = kA\frac{\Delta T}{L}",),
            substitutions=(
                rf"Q/t = {p['thermal_conductivity']:g} \cdot {p['area']:g} \cdot "
                rf"\frac{{{abs(p['delta_temp']):g}}}{{{p['L']:g}}}",
            ),
            quantities=(QuantityResult("", value, "W"),),
        )

    if op == "linear_expansion":
        if p["L0"] <= 0 or p["alpha"] < 0:
            raise SolveServiceError("linear expansion needs positive length and nonnegative alpha")
        expansion = p["alpha"] * p["L0"] * p["delta_temp"]
        return PhysicsResult(
            answer=(
                rf"\Delta L = \alpha L_0 \Delta T = {p['alpha']:g} \cdot "
                rf"{p['L0']:g} \cdot {p['delta_temp']:g} "
                rf"\approx {expansion:g} \text{{ m}}"
            ),
            formulas=(r"\Delta L = \alpha L_0 \Delta T",),
            substitutions=(
                rf"\Delta L = {p['alpha']:g} \cdot {p['L0']:g} \cdot {p['delta_temp']:g}",
            ),
            quantities=(QuantityResult("", expansion, "m"),),
        )

    if op == "latent_heat":
        if p["m"] < 0 or p["latent_heat"] < 0:
            raise SolveServiceError("latent heat needs nonnegative mass and specific latent heat")
        heat = p["m"] * p["latent_heat"]
        return PhysicsResult(
            answer=(
                rf"Q = mL = {p['m']:g} \cdot {p['latent_heat']:g} "
                rf"\approx {heat:g} \text{{ J}}"
            ),
            formulas=(r"Q = mL",),
            substitutions=(rf"Q = {p['m']:g} \cdot {p['latent_heat']:g}",),
            quantities=(QuantityResult("", heat, "J"),),
        )

    if op == "first_law_internal_energy":
        change = p["heat"] - p["W"]
        return PhysicsResult(
            answer=(
                rf"\Delta U = Q - W = {p['heat']:g} - {p['W']:g} "
                rf"\approx {change:g} \text{{ J}}"
            ),
            formulas=(r"\Delta U = Q - W",),
            substitutions=(rf"\Delta U = {p['heat']:g} - {p['W']:g}",),
            quantities=(QuantityResult("", change, "J"),),
        )

    if op == "heat_energy":
        return _heat_energy(intent, p)

    if op == "ideal_gas_pressure":
        volume = p["volume"]
        if volume <= 0:
            raise SolveServiceError("volume must be positive")
        if p["temp"] <= 0:
            raise SolveServiceError("an absolute temperature must be positive")
        pressure = p["moles"] * _GAS_CONSTANT * p["temp"] / volume
        return PhysicsResult(
            answer=(
                rf"P = \frac{{nRT}}{{V}} = \frac{{{p['moles']:g} \cdot {_GAS_CONSTANT:.4f} "
                rf"\cdot {p['temp']:g}}}{{{volume:g}}} \approx {pressure:.2f} \text{{ Pa}}"
            ),
            formulas=(r"P = \frac{nRT}{V}",),
            substitutions=(
                rf"P = \frac{{{p['moles']:g} \cdot {_GAS_CONSTANT:.4f} \cdot {p['temp']:g}}}"
                rf"{{{volume:g}}}",
            ),
            quantities=(QuantityResult("", pressure, "Pa"),),
        )

    if op == "thermal_efficiency":
        supplied = p["Q_in"]
        if supplied <= 0:
            raise SolveServiceError("the energy supplied must be positive")
        eta = p["W_out"] / supplied
        return PhysicsResult(
            answer=(
                rf"\eta = \frac{{W}}{{Q_{{in}}}} = \frac{{{p['W_out']:g}}}{{{supplied:g}}} "
                rf"\approx {eta:.2f} \; ({eta * 100:.1f}\%)"
            ),
            formulas=(r"\eta = \frac{W}{Q_{in}}",),
            substitutions=(rf"\eta = \frac{{{p['W_out']:g}}}{{{supplied:g}}}",),
            quantities=(
                QuantityResult(
                    "",
                    eta,
                    "",
                    detail=f"{eta * 100:.1f}%",
                ),
            ),
        )

    raise SolveServiceError(f"unsupported thermal op: {op}")


def solve_fluids(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "mass_flow_rate":
        if p["rho"] <= 0 or p["area"] <= 0:
            raise SolveServiceError("mass flow rate needs positive density and area")
        value = p["rho"] * p["area"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"\dot{{m}} = \rho Av = {p['rho']:g} \cdot {p['area']:g} \cdot "
                rf"{p['v']:g} \approx {value:.4g} \text{{ kg/s}}"
            ),
            formulas=(r"\dot{m} = \rho Av",),
            substitutions=(rf"\dot{{m}} = {p['rho']:g} \cdot {p['area']:g} \cdot {p['v']:g}",),
            quantities=(QuantityResult("", value, "kg/s"),),
        )

    if op == "torricelli_speed":
        if p["depth"] < 0 or p["g"] <= 0:
            raise SolveServiceError("Torricelli speed needs nonnegative head and positive gravity")
        value = math.sqrt(2 * p["g"] * p["depth"])
        return PhysicsResult(
            answer=(
                rf"v = \sqrt{{2gh}} = \sqrt{{2 \cdot {p['g']:g} \cdot {p['depth']:g}}} "
                rf"\approx {value:.4g} \text{{ m/s}}"
            ),
            formulas=(r"v = \sqrt{2gh}",),
            substitutions=(rf"v = \sqrt{{2 \cdot {p['g']:g} \cdot {p['depth']:g}}}",),
            quantities=(QuantityResult("", value, "m/s"),),
        )

    if op == "stokes_drag":
        if p["viscosity"] < 0 or p["r"] <= 0 or p["v"] < 0:
            raise SolveServiceError("Stokes drag needs valid viscosity, radius, and speed")
        value = 6 * math.pi * p["viscosity"] * p["r"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"F_d = 6\pi\eta rv = 6\pi \cdot {p['viscosity']:g} \cdot "
                rf"{p['r']:g} \cdot {p['v']:g} \approx {value:.4g} \text{{ N}}"
            ),
            formulas=(r"F_d = 6\pi\eta rv",),
            substitutions=(
                rf"F_d = 6\pi \cdot {p['viscosity']:g} \cdot {p['r']:g} \cdot {p['v']:g}",
            ),
            quantities=(QuantityResult("", value, "N"),),
        )

    if op == "reynolds_number":
        if p["viscosity"] <= 0 or p["rho"] <= 0 or p["L"] <= 0:
            raise SolveServiceError("Reynolds number needs positive density, length, and viscosity")
        value = p["rho"] * p["v"] * p["L"] / p["viscosity"]
        return PhysicsResult(
            answer=(
                rf"Re = \frac{{\rho vL}}{{\eta}} = "
                rf"\frac{{{p['rho']:g} \cdot {p['v']:g} \cdot {p['L']:g}}}"
                rf"{{{p['viscosity']:g}}} \approx {value:.4g}"
            ),
            formulas=(r"Re = \frac{\rho vL}{\eta}",),
            substitutions=(
                rf"Re = \frac{{{p['rho']:g} \cdot {p['v']:g} \cdot {p['L']:g}}}"
                rf"{{{p['viscosity']:g}}}",
            ),
            quantities=(QuantityResult("", value, ""),),
        )

    if op == "surface_tension":
        if p["L"] <= 0:
            raise SolveServiceError("contact length must be positive")
        value = p["F"] / p["L"]
        return PhysicsResult(
            answer=(
                rf"\gamma = \frac{{F}}{{L}} = \frac{{{p['F']:g}}}{{{p['L']:g}}} "
                rf"\approx {value:.4g} \text{{ N/m}}"
            ),
            formulas=(r"\gamma = \frac{F}{L}",),
            substitutions=(rf"\gamma = \frac{{{p['F']:g}}}{{{p['L']:g}}}",),
            quantities=(QuantityResult("", value, "N/m"),),
        )

    if op == "laplace_pressure":
        if p["surface_tension"] < 0 or p["r"] <= 0:
            raise SolveServiceError("Laplace pressure needs valid surface tension and radius")
        value = p["mode_factor"] * p["surface_tension"] / p["r"]
        symbolic = (
            r"\Delta P = \frac{4\gamma}{r}"
            if p["mode_factor"] == 4
            else r"\Delta P = \frac{2\gamma}{r}"
        )
        plugged = rf"\frac{{{p['mode_factor']:g} \cdot {p['surface_tension']:g}}}{{{p['r']:g}}}"
        return PhysicsResult(
            answer=rf"{symbolic} = {plugged} \approx {value:.4g} \text{{ Pa}}",
            formulas=(symbolic,),
            substitutions=(rf"\Delta P = {plugged}",),
            quantities=(QuantityResult("", value, "Pa"),),
        )

    if op == "hydraulic_force":
        if p["A1"] <= 0 or p["A2"] <= 0:
            raise SolveServiceError("hydraulic force needs positive piston areas")
        force = p["F1"] * p["A2"] / p["A1"]
        return PhysicsResult(
            answer=(
                rf"\frac{{F_1}}{{A_1}} = \frac{{F_2}}{{A_2}} \Rightarrow "
                rf"F_2 = \frac{{F_1A_2}}{{A_1}} = "
                rf"\frac{{{p['F1']:g} \cdot {p['A2']:g}}}{{{p['A1']:g}}} "
                rf"\approx {force:g} \text{{ N}}"
            ),
            formulas=(r"F_2 = \frac{F_1A_2}{A_1}",),
            substitutions=(rf"F_2 = \frac{{{p['F1']:g} \cdot {p['A2']:g}}}{{{p['A1']:g}}}",),
            quantities=(QuantityResult("", force, "N"),),
        )

    if op == "bernoulli_pressure":
        if p["rho"] <= 0 or p["pres1"] < 0:
            raise SolveServiceError("Bernoulli pressure needs positive density and valid pressure")
        gravity = p.get("g", 9.81)
        pressure = p["pres1"] + 0.5 * p["rho"] * (p["v1"] ** 2 - p["v2"] ** 2)
        if "h1" in p and "h2" in p:
            pressure += p["rho"] * gravity * (p["h1"] - p["h2"])
        if pressure < 0:
            raise SolveServiceError(
                "the stated ideal-flow values imply a negative absolute pressure"
            )
        if "h1" in p and "h2" in p:
            return PhysicsResult(
                answer=(
                    r"P_1 + \frac{1}{2}\rho v_1^2 + \rho g h_1 = "
                    r"P_2 + \frac{1}{2}\rho v_2^2 + \rho g h_2 "
                    r"\Rightarrow P_2 = P_1 + \frac{1}{2}\rho(v_1^2-v_2^2)"
                    rf" + \rho g(h_1-h_2) \approx {pressure:g} \text{{ Pa}}"
                ),
                formulas=(r"P_2 = P_1 + \frac{1}{2}\rho(v_1^2-v_2^2) + \rho g(h_1-h_2)",),
                substitutions=(
                    rf"P_2 = {p['pres1']:g} + \frac{{1}}{{2}} \cdot {p['rho']:g} \cdot "
                    rf"({p['v1']:g}^2 - {p['v2']:g}^2) + {p['rho']:g} \cdot {gravity:g} \cdot "
                    rf"({p['h1']:g} - {p['h2']:g})",
                ),
                quantities=(QuantityResult("", pressure, "Pa"),),
            )
        return PhysicsResult(
            answer=(
                r"P_1 + \frac{1}{2}\rho v_1^2 = P_2 + \frac{1}{2}\rho v_2^2 "
                r"\Rightarrow P_2 = P_1 + \frac{1}{2}\rho(v_1^2-v_2^2) = "
                rf"{p['pres1']:g} + \frac{{1}}{{2}} \cdot {p['rho']:g} "
                rf"\cdot ({p['v1']:g}^2 - {p['v2']:g}^2) "
                rf"\approx {pressure:g} \text{{ Pa}}"
            ),
            formulas=(r"P_2 = P_1 + \frac{1}{2}\rho(v_1^2-v_2^2)",),
            substitutions=(
                rf"P_2 = {p['pres1']:g} + \frac{{1}}{{2}} \cdot {p['rho']:g} \cdot ({p['v1']:g}^2 "
                rf"- {p['v2']:g}^2)",
            ),
            quantities=(QuantityResult("", pressure, "Pa"),),
        )

    if op == "pressure_from_force":
        area = p["area"]
        if area <= 0:
            raise SolveServiceError("area must be positive")
        pressure = p["F"] / area
        return PhysicsResult(
            answer=(
                rf"P = \frac{{F}}{{A}} = \frac{{{p['F']:g}}}{{{area:g}}} "
                rf"\approx {pressure:.2f} \text{{ Pa}}"
            ),
            formulas=(r"P = \frac{F}{A}",),
            substitutions=(rf"P = \frac{{{p['F']:g}}}{{{area:g}}}",),
            quantities=(QuantityResult("", pressure, "Pa"),),
        )

    if op == "pressure_at_depth":
        pressure = p["rho"] * p.get("g", 9.81) * p["depth"]
        return PhysicsResult(
            answer=(
                rf"P = \rho g h = {p['rho']:g} \cdot {p.get('g', 9.81):g} \cdot "
                rf"{p['depth']:g} \approx {pressure:.2f} \text{{ Pa}}"
            ),
            formulas=(r"P = \rho g h",),
            substitutions=(rf"P = {p['rho']:g} \cdot {p.get('g', 9.81):g} \cdot {p['depth']:g}",),
            # Gauge, and it says so: the absolute reading is this plus one
            # atmosphere, and which one is meant changes the number by 101 kPa.
            quantities=(QuantityResult("", pressure, "Pa", detail="gauge"),),
        )

    if op == "upthrust":
        force = p["rho"] * p["volume"] * p.get("g", 9.81)
        return PhysicsResult(
            answer=(
                rf"F_b = \rho V g = {p['rho']:g} \cdot {p['volume']:g} \cdot "
                rf"{p.get('g', 9.81):g} \approx {force:.2f} \text{{ N}}"
            ),
            formulas=(r"F_b = \rho V g",),
            substitutions=(
                rf"F_b = {p['rho']:g} \cdot {p['volume']:g} \cdot {p.get('g', 9.81):g}",
            ),
            quantities=(QuantityResult("", force, "N"),),
            # The one fluids answer a free body actually draws: an upward
            # buoyant force against the weight it opposes.
            simulation_specs=_free_body_scene(
                [
                    SimulationVector(
                        anchor=[0.0, 0.0],
                        dx=0.0,
                        dy=1.0,
                        label=f"upthrust {plain_number(force)} N",
                        role="force",
                    ),
                    SimulationVector(
                        anchor=[0.0, 0.0], dx=0.0, dy=-1.0, label="weight", role="force"
                    ),
                ],
                label="body",
            ),
        )

    if op == "density":
        volume = p["volume"]
        if volume <= 0:
            raise SolveServiceError("volume must be positive")
        rho = p["m"] / volume
        return PhysicsResult(
            answer=(
                rf"\rho = \frac{{m}}{{V}} = \frac{{{p['m']:g}}}{{{volume:g}}} "
                rf"\approx {rho:.2f} \text{{ kg/m}}^3"
            ),
            formulas=(r"\rho = \frac{m}{V}",),
            substitutions=(rf"\rho = \frac{{{p['m']:g}}}{{{volume:g}}}",),
            quantities=(QuantityResult("", rho, "kg/m^3"),),
        )

    if op == "continuity_velocity":
        a2 = p["A2"]
        if a2 <= 0:
            raise SolveServiceError("the second area must be positive")
        v2 = p["A1"] * p["v"] / a2
        return PhysicsResult(
            answer=(
                rf"A_1 v_1 = A_2 v_2 \Rightarrow v_2 = \frac{{{p['A1']:g} \cdot "
                rf"{p['v']:g}}}{{{a2:g}}} \approx {v2:.2f} \text{{ m/s}}"
            ),
            formulas=(r"v_2 = \frac{A_1 v_1}{A_2}",),
            substitutions=(rf"v_2 = \frac{{{p['A1']:g} \cdot {p['v']:g}}}{{{a2:g}}}",),
            quantities=(QuantityResult("", v2, "m/s"),),
        )

    if op == "flow_rate":
        flow = p["area"] * p["v"]
        return PhysicsResult(
            answer=(
                rf"Q = A v = {p['area']:g} \cdot {p['v']:g} \approx {flow:.4g} "
                rf"\text{{ m}}^3\text{{/s}}"
            ),
            formulas=(r"Q = A v",),
            substitutions=(rf"Q = {p['area']:g} \cdot {p['v']:g}",),
            quantities=(QuantityResult("", flow, "m^3/s"),),
        )

    raise SolveServiceError(f"unsupported fluids op: {op}")


def solve_materials(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "stress":
        area = p["area"]
        if area <= 0:
            raise SolveServiceError("area must be positive")
        value = p["F"] / area
        return PhysicsResult(
            answer=(
                rf"\sigma = \frac{{F}}{{A}} = \frac{{{p['F']:g}}}{{{area:g}}} "
                rf"\approx {value:.4g} \text{{ Pa}}"
            ),
            formulas=(r"\sigma = \frac{F}{A}",),
            substitutions=(rf"\sigma = \frac{{{p['F']:g}}}{{{area:g}}}",),
            quantities=(QuantityResult("", value, "Pa"),),
        )

    if op == "strain":
        original = p["L0"]
        if original <= 0:
            raise SolveServiceError("the original length must be positive")
        value = p["dL"] / original
        return PhysicsResult(
            answer=(
                rf"\varepsilon = \frac{{\Delta L}}{{L_0}} = "
                rf"\frac{{{p['dL']:g}}}{{{original:g}}} \approx {value:.4g}"
            ),
            formulas=(r"\varepsilon = \frac{\Delta L}{L_0}",),
            substitutions=(rf"\varepsilon = \frac{{{p['dL']:g}}}{{{original:g}}}",),
            quantities=(QuantityResult("", value, ""),),
        )

    if op == "youngs_modulus":
        strain = p["strain"]
        if strain == 0:
            raise SolveServiceError("strain cannot be zero")
        value = p["sigma"] / strain
        return PhysicsResult(
            answer=(
                rf"E = \frac{{\sigma}}{{\varepsilon}} = "
                rf"\frac{{{p['sigma']:g}}}{{{strain:g}}} \approx {value:.4g} \text{{ Pa}}"
            ),
            formulas=(r"E = \frac{\sigma}{\varepsilon}",),
            substitutions=(rf"E = \frac{{{p['sigma']:g}}}{{{strain:g}}}",),
            quantities=(QuantityResult("", value, "Pa"),),
        )

    raise SolveServiceError(f"unsupported materials op: {op}")
