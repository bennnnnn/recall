"""Verified quantum operations: photons, the photoelectric effect, atoms, statistics."""

from __future__ import annotations

from app.modules.physics.catalog.spec import Binding, FormulaSpec, FormulaVariant, formula, var

_FREQ = var("freq", "f", "hertz")
_WAVELENGTH = var("wavelength", r"\lambda", "meter")
_WORK_FUNCTION = var("work_function", r"\phi", "joule")
_PHOTOELECTRIC = ("work function", "photoelectr", "metal surface")
_HYDROGEN = ("hydrogen",)
# "falls from n = 3 to n = 2": either order is one photon of one energy.
_N_UPPER = var("n_upper", "n_u", dimensionless=True, words=("from",))
_N_LOWER = var("n_lower", "n_l", dimensionless=True, words=("to",))
_LEVELS = r"\left(\frac{1}{n_l^2} - \frac{1}{n_u^2}\right)"
_LEVELS_EXPRESSION = "(1/n_lower**2 - 1/n_upper**2)"


def _transition(
    operation: str,
    symbol: str,
    base: str,
    expression: str,
    asks: tuple[str, ...],
    result: str,
) -> FormulaSpec:
    return formula(
        operation,
        "modern",
        "Rydberg formula",
        symbol,
        base_latex=base,
        assumptions=("hydrogen, infinite nuclear mass",),
        expression=expression,
        variables=(_N_LOWER, _N_UPPER),
        binding=Binding(
            asks=asks,
            result=(result,),
            inputs=(frozenset({"n_lower", "n_upper"}),),
            cues=_HYDROGEN,
            descending=("n_upper", "n_lower"),
            nonnegative=True,
        ),
    )


SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "photon_momentum",
        "modern",
        "Photon momentum",
        "p",
        base_latex=r"p = \frac{h}{\lambda}",
        expression="h_planck/wavelength",
        variants=(
            FormulaVariant(
                present=frozenset({"freq"}),
                latex=r"p = \frac{hf}{c}",
                expression="h_planck*freq/c_light",
            ),
        ),
        variables=(_FREQ, _WAVELENGTH),
        binding=Binding(
            asks=("momentum",),
            result=("kilogram * meter / second",),
            inputs=(frozenset({"wavelength"}), frozenset({"freq"})),
            cues=("photon", "light"),
            nonnegative=True,
        ),
    ),
    formula(
        "threshold_frequency",
        "modern",
        "Photoelectric threshold",
        "f_0",
        base_latex=r"hf_0 = \phi",
        expression="work_function/h_planck",
        variables=(_WORK_FUNCTION,),
        binding=Binding(
            asks=(
                "threshold frequency",
                "minimum frequency",
                "cut-off frequency",
                "cutoff frequency",
            ),
            result=("hertz",),
            inputs=(frozenset({"work_function"}),),
            nonnegative=True,
        ),
    ),
    formula(
        "threshold_wavelength",
        "modern",
        "Photoelectric threshold",
        r"\lambda_0",
        base_latex=r"\frac{hc}{\lambda_0} = \phi",
        expression="h_planck*c_light/work_function",
        variables=(_WORK_FUNCTION,),
        binding=Binding(
            asks=(
                "threshold wavelength",
                "maximum wavelength",
                "longest wavelength",
                "cut-off wavelength",
                "cutoff wavelength",
            ),
            result=("meter",),
            inputs=(frozenset({"work_function"}),),
            nonnegative=True,
        ),
    ),
    formula(
        "stopping_potential",
        "modern",
        "Photoelectric equation",
        "V_s",
        base_latex=r"eV_s = hf - \phi",
        expression="(h_planck*freq - work_function)/e_charge",
        variants=(
            FormulaVariant(
                present=frozenset({"wavelength"}),
                latex=r"eV_s = \frac{hc}{\lambda} - \phi",
                expression="(h_planck*c_light/wavelength - work_function)/e_charge",
            ),
        ),
        variables=(_FREQ, _WAVELENGTH, _WORK_FUNCTION),
        binding=Binding(
            asks=("stopping potential", "stopping voltage"),
            result=("volt",),
            inputs=(
                frozenset({"freq", "work_function"}),
                frozenset({"wavelength", "work_function"}),
            ),
            cues=_PHOTOELECTRIC,
            # Below the threshold no electron leaves, so there is nothing to stop.
            nonnegative=True,
        ),
    ),
    formula(
        "quantum_oscillator_energy",
        "modern",
        "Quantum harmonic oscillator",
        "E_n",
        base_latex=r"E_n = \left(n + \tfrac{1}{2}\right)\hbar\omega",
        expression="(quantum_n + 1/2)*hbar*omega",
        variants=(
            FormulaVariant(
                present=frozenset({"freq"}),
                latex=r"E_n = \left(n + \tfrac{1}{2}\right)hf",
                expression="(quantum_n + 1/2)*h_planck*freq",
            ),
        ),
        variables=(
            _FREQ,
            var("omega", r"\omega", "radian / second"),
            var(
                "quantum_n",
                "n",
                dimensionless=True,
                implied=(
                    ("ground state", 0.0),
                    ("first excited state", 1.0),
                    ("second excited state", 2.0),
                    ("third excited state", 3.0),
                ),
            ),
        ),
        binding=Binding(
            asks=("energy",),
            result=("joule",),
            inputs=(frozenset({"omega", "quantum_n"}), frozenset({"freq", "quantum_n"})),
            cues=("harmonic oscillator", "quantum oscillator"),
            nonnegative=True,
        ),
    ),
    _transition(
        "hydrogen_transition_wavelength",
        r"\lambda",
        rf"\frac{{1}}{{\lambda}} = R_\infty{_LEVELS}",
        f"1/(R_inf*{_LEVELS_EXPRESSION})",
        ("wavelength",),
        "meter",
    ),
    _transition(
        "hydrogen_transition_energy",
        r"\Delta E",
        rf"\Delta E = hcR_\infty{_LEVELS}",
        f"h_planck*c_light*R_inf*{_LEVELS_EXPRESSION}",
        ("energy",),
        "joule",
    ),
    formula(
        "bohr_orbit_radius",
        "modern",
        "Bohr model",
        "r_n",
        base_latex=r"r_n = n^2 a_0",
        assumptions=("hydrogen",),
        expression="quantum_n**2*a_0",
        variables=(
            var(
                "quantum_n",
                "n",
                dimensionless=True,
                implied=(("ground state", 1.0), ("first excited state", 2.0)),
            ),
        ),
        binding=Binding(
            asks=("radius", "orbit radius", "orbital radius"),
            result=("meter",),
            inputs=(frozenset({"quantum_n"}),),
            cues=("bohr", "hydrogen"),
            nonnegative=True,
        ),
    ),
    formula(
        "boltzmann_population_ratio",
        "modern",
        "Boltzmann distribution",
        r"\frac{N_2}{N_1}",
        base_latex=r"\frac{N_2}{N_1} = e^{-\Delta E/k_B T}",
        assumptions=("two non-degenerate levels in thermal equilibrium",),
        expression="exp(-energy_gap/(k_B*temp))",
        variables=(var("energy_gap", r"\Delta E", "joule"), var("temp", "T", "kelvin")),
        binding=Binding(
            asks=("ratio", "population ratio", "fraction"),
            result=("dimensionless",),
            inputs=(frozenset({"energy_gap", "temp"}),),
            cues=("boltzmann", "population"),
            nonnegative=True,
        ),
    ),
    formula(
        "boltzmann_entropy",
        "modern",
        "Boltzmann entropy",
        "S",
        base_latex=r"S = k_B \ln \Omega",
        expression="k_B*log(microstates)",
        variables=(var("microstates", r"\Omega", dimensionless=True),),
        binding=Binding(
            asks=("entropy",),
            result=("joule / kelvin",),
            inputs=(frozenset({"microstates"}),),
            cues=("microstate",),
            nonnegative=True,
        ),
    ),
    formula(
        "energy_time_uncertainty",
        "modern",
        "Heisenberg uncertainty principle",
        r"\Delta E_{min}",
        base_latex=r"\Delta E \, \Delta t \geq \frac{\hbar}{2}",
        expression="hbar/(2*dt)",
        variables=(var("dt", r"\Delta t", "second"),),
        binding=Binding(
            asks=(
                "uncertainty in energy",
                "uncertainty in the energy",
                "energy uncertainty",
                "minimum uncertainty",
                "energy width",
            ),
            result=("joule",),
            inputs=(frozenset({"dt"}),),
            cues=("uncertainty", "lifetime"),
            nonnegative=True,
        ),
    ),
)
