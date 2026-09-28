"""Structured physics I/O — validated before SymPy and fence emission.

Split out of ``MathIntent`` (see docs/SUBJECT_SEPARATION_TICKETS.md, S1): physics's real
footprint on the old shared model was narrow — ``kind`` (twenty of its forty-nine values),
``operation`` (always ``"solve"``), and the three ``physics_*`` fields. Everything else on
``MathIntent`` (``lhs``/``rhs``, ``school_op``, geometry dimensions, ...) is genuinely
math's, not physics's, and stays there.

``PhysicsIntent`` flows only through the physics-owned extractor, block builder, solver,
and presentation boundary. The subject-neutral chat dispatcher may carry either a math
or physics result, but neither subject imports or registers the other's algorithms.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ProjectileQuantity = Literal["time_of_flight", "max_height", "range", "impact_speed"]


class PhysicsIntent(BaseModel):
    kind: Literal[
        "kinematics",
        "projectile",
        "force",
        "energy",
        "momentum",
        "friction",
        "circular",
        "spring",
        "circuit",
        "torque",
        "suvat",
        "waves",
        "optics",
        "thermal",
        "gravitation",
        "fluids",
        "rotation",
        "magnetism",
        "materials",
        "modern",
    ]
    # Physics never sets anything but "solve" — narrower than MathIntent.operation
    # on purpose, but the same field name so generic dispatch code that reads
    # `.operation` on "whichever intent an extractor returned" (e.g.
    # `direct_calculus.py`'s `actual.operation == "dsolve"`) never needs to know
    # or care which of the two types it was handed.
    operation: Literal["solve"] = "solve"
    # The model sets up the equation with known values; SymPy solves symbolically; the SVG
    # engine renders the trajectory. See modules/physics/extract.py extractors and
    # modules/physics/solver.py solvers.
    physics_op: (
        Literal[
            "position",
            "velocity",
            "speed",
            "acceleration",
            "average_speed",
            "rate_speed",
            "rate_distance",
            "rate_time",
            "time_to_ground",
            "vertical_max_height",
            "range",
            "max_height",
            # A projectile question that is not about distance. Before these
            # existed the extractor defaulted to "range", so "how long is it in
            # the air" was answered with a length.
            "time_of_flight",
            "impact_speed",
            "launch_angle",
            "net_force",
            # Rope/pulley free bodies. P2 refused these on purpose after
            # finding them answered with m*a; these are the shapes now solved.
            "tension",
            "atwood",
            # Vector forces. Everything else on the force kind is scalar.
            "resultant_force",
            "resolve_force",
            "kinetic_energy",
            "potential_energy",
            "work",
            "power",
            "mechanical_efficiency",
            "work_energy",
            "mechanical_energy_gravity",
            "mechanical_energy_spring",
            "momentum",
            "impulse",
            "final_velocity",
            "center_of_mass",
            "friction_force",
            "normal_force",
            "incline_acceleration",
            # Round 3.
            "friction_coefficient",
            "minimum_force",
            "centripetal_force",
            "centripetal_acceleration",
            "orbital_period",
            # Circular motion: ω = v/r, or a spin rate in revolutions per minute.
            "angular_velocity",
            "spring_force",
            "spring_energy",
            "shm_period",
            # Same simple harmonic motion, different period formula, so it
            # lives on the spring kind rather than a kind of its own.
            "pendulum_period",
            # Round 3. Never a bare "frequency" - the waves kind has one too.
            "shm_frequency",
            "shm_max_speed",
            "voltage",
            "current",
            "resistance",
            "electrical_power",
            "series_resistance",
            "parallel_resistance",
            # Round 3. "electrical_energy" rather than "energy": the mechanical
            # kind already owns work and kinetic energy, and both are joules.
            "charge",
            "electrical_energy",
            "capacitance",
            "parallel_plate_capacitance",
            "capacitor_energy",
            "rc_time_constant",
            "terminal_voltage",
            "kirchhoff_junction",
            "kirchhoff_loop",
            "inductor_emf",
            "inductor_energy",
            "rl_time_constant",
            "rl_growth",
            "rl_decay",
            "rms_voltage",
            "rms_current",
            "inductive_reactance",
            "capacitive_reactance",
            "series_impedance",
            "lc_resonance",
            "ac_average_power",
            "torque",
            "moment_balance",
            "lever_arm",
            "net_torque",
            # SUVAT — the op names the unknown, and the solver picks whichever
            # of the four equations the givens support (P8's approach).
            # Round 3 waves. Never a bare "frequency" or "period": the spring
            # kind has both.
            "wave_speed",
            "wavelength",
            "wave_frequency",
            "wave_frequency_from_period",
            "wave_period",
            "doppler_frequency",
            "string_wave_speed",
            "resonance_frequency",
            "sound_intensity",
            "beat_frequency",
            # Round 3 optics. "lens_power" would be a fourth thing called
            # power; it is not solved here, so it does not exist.
            "image_distance",
            "magnification",
            "refractive_index",
            "critical_angle",
            "lens_power",
            "double_slit_fringe_spacing",
            "diffraction_central_width",
            "malus_intensity",
            "brewster_angle",
            # Round 3 thermal.
            "heat_energy",
            "ideal_gas_pressure",
            "thermal_efficiency",
            "linear_expansion",
            "latent_heat",
            "first_law_internal_energy",
            "carnot_efficiency",
            "entropy_change",
            "ideal_gas_volume",
            "ideal_gas_amount",
            "ideal_gas_temperature",
            "monatomic_energy",
            "isobaric_work",
            "adiabatic_pressure",
            "adiabatic_volume",
            "refrigerator_cop",
            "heat_pump_cop",
            # Round 3 gravitation.
            "gravitational_force",
            "orbital_velocity",
            "escape_velocity",
            "surface_gravity",
            "gravitational_potential",
            "gravitational_potential_energy",
            "orbital_energy",
            "kepler_period",
            # Round 3 fluids. "pressure_from_force" and "pressure_at_depth"
            # rather than "pressure" and "fluid_pressure": in a Literal this
            # long, a pair that close reads wrong.
            "pressure_from_force",
            "pressure_at_depth",
            "upthrust",
            "density",
            "continuity_velocity",
            "flow_rate",
            "hydraulic_force",
            "bernoulli_pressure",
            "poiseuille_flow",
            "mass_flow_rate",
            "torricelli_speed",
            "stokes_drag",
            "reynolds_number",
            "surface_tension",
            "laplace_pressure",
            # Rotation: ω = θ/t. A different measurement from circular v/r.
            "angular_displacement_rate",
            "moment_of_inertia",
            "angular_momentum",
            "rotational_kinetic_energy",
            "rotational_omega",
            "rotational_theta",
            "rotational_alpha",
            "torque_inertia",
            "torque_angular_impulse",
            "angular_momentum_conservation",
            "rolling_speed",
            "rolling_acceleration",
            "rolling_kinetic_energy",
            "parallel_axis",
            # Round 3 magnetism. Never a bare "force": three kinds have one.
            "electric_force",
            "magnetic_force_wire",
            "magnetic_force_charge",
            "magnetic_flux",
            "electric_field",
            "electric_potential",
            "electric_potential_energy",
            "charged_particle_radius",
            "motional_emf",
            "magnetic_field_wire",
            "gauss_outside",
            "gauss_inside_shell",
            "gauss_inside_sphere",
            "gauss_line",
            "gauss_plane",
            "faraday_emf",
            # Round 3 materials. "stress" stays bare because it is the physics
            # word; the kind is what separates it from a fluid pressure, and a
            # test pins each to its own.
            "stress",
            "strain",
            "youngs_modulus",
            # Round 3 modern. Never a bare "energy": four kinds have one.
            "photon_energy",
            "de_broglie_wavelength",
            "lorentz_factor",
            "time_dilation",
            "length_contraction",
            "photoelectric_kinetic_energy",
            "uncertainty_momentum",
            "particle_box_energy",
            "hydrogen_energy_level",
            "compton_shift",
            "wien_peak",
            "stefan_boltzmann_power",
            "heat_conduction_rate",
            "half_life_remaining",
            "mass_energy",
            "suvat_velocity",
            "suvat_distance",
            "suvat_time",
            "suvat_acceleration",
        ]
        | None
    ) = None
    # Initial conditions / knowns: {"h0": 20.0, "v0": 0.0, "g": 9.81, ...}.
    # Keys are the canonical variable names the solver expects.
    physics_params: dict[str, float] | None = None
    # Unit labels for the params above: {"h0": "m", "v0": "m/s", "g": "m/s^2"}.
    # Used to render the answer with proper units.
    physics_units: dict[str, str] | None = None
    # One launch, with every requested output retained in presentation order.
    requested_ops: list[ProjectileQuantity] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def coherent_requested_ops(self) -> PhysicsIntent:
        ops = self.requested_ops
        if ops:
            if self.kind != "projectile" or self.physics_op != ops[0]:
                raise ValueError("multipart quantities must belong to the same projectile")
            if len(ops) < 2 or len(set(ops)) != len(ops):
                raise ValueError("multipart quantities must contain two to four distinct requests")
        self._catalog_owns_operation()
        return self

    def _catalog_owns_operation(self) -> None:
        """Reject a kind, operation, or parameter the formula catalog does not contain.

        The catalog declares each operation and the variables it accepts. The
        ``physics_op`` literal is the typed mirror of those ids; a test keeps
        the two sets identical. The catalog does not import this module.
        """
        if self.physics_op is None:
            return
        from app.modules.physics.catalog import CATALOG

        spec = CATALOG.get(self.physics_op)
        if spec is None or spec.kind != self.kind:
            raise ValueError(f"{self.kind} does not define {self.physics_op}")
        allowed = {variable.name for variable in spec.variables}
        params = set(self.physics_params or {})
        unknown = params - allowed
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"{self.physics_op} does not declare {names}")
        extra_units = set(self.physics_units or {}) - params
        if extra_units:
            names = ", ".join(sorted(extra_units))
            raise ValueError(f"{self.physics_op} units are not parameters: {names}")
