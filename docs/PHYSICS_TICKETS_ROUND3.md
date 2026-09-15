# Recall — Physics Tickets, Round 3 (Sep 2026)

Follow-up to [PHYSICS_TICKETS.md](./PHYSICS_TICKETS.md) (P1–P10, shipped in
[#1324](https://github.com/bennnnnn/recall/pull/1324)) and
[PHYSICS_TICKETS_ROUND2.md](./PHYSICS_TICKETS_ROUND2.md) (P11–P17, shipped in
[#1335](https://github.com/bennnnnn/recall/pull/1335)).

Same method as rounds 1 and 2: every claim here was produced by driving the
real pipeline (`needs_symbolic` → `extract_math_intent` → `solve_physics` →
`_build_verified_block`), not by reading it.

**What prompted this round.** A 50-question syllabus sweep answered **3**, and
**2 of those 3 were wrong**. Rounds 1 and 2 grew *mechanics*; every remaining
gap was a different branch of the subject.

| Before | After |
|---|---|
| 3 of 50 answered, 2 of them wrong | **48 of 50**, none wrong |
| 11 verified kinds | **20** |
| 42 verified ops | **89** |

The two still refused are refused on purpose: latent heat (melting is not
`Q = mc dT`, and reaching for `c` would be a wrong number) and a 2D collision
(P11 — the number needs both post-collision angles).

## Seven wrong answers, not one

The sweep was commissioned to find coverage gaps. It found those, but the
expensive finds were the wrong answers hiding inside topics that already
worked — six of the seven were in code that shipped in rounds 1 and 2 and
passed their tests.

| # | Question | Answered | Should be |
|---|---|---|---|
| 1 | time of flight, thrown 20 m/s at 30° | `35.31 m` | `2.04 s` |
| 2 | how fast when it lands, same throw | `35.31 m` | `20.00 m/s` |
| 3 | how long until it hits the ground, same throw | `4.08 s` | `2.04 s` |
| 4 | `2, 3 and 5 ohms in series` | `5.00 Ω` | `10.00 Ω` |
| 5 | `4, 6 and 12 ohms in parallel` | `2.40 Ω` | `2.00 Ω` |
| 6 | g on a planet of mass `6e24 kg`, radius `6.4e6 m` | `0.00 m/s²` | `9.78 m/s²` |
| 7 | orbital velocity 400 km above the earth | `7909.81 m/s` | `7672.62 m/s` |

Each has a different cause and they are worth reading as a set, because four of
the seven are the same mistake in different clothes — **a value silently
standing in for one it is not**:

1–2. **The projectile op was an initializer, not a branch.**
   `op: Literal["range", "max_height"] = "range"`, so any question that cleared
   the cue gate and did not say "height" was answered with the horizontal
   range. Fixed by adopting SUVAT's shape: a phrasing → op table, and a
   question the table does not recognise is *refused*.

3. **Kinematics ran first and had no angle.** It claimed "launched at 20 m/s at
   30 degrees, how long until it hits the ground" and used the whole 20 m/s as
   the vertical component. It now defers on a launch-angle signature, the way
   it already defers on a non-gravity acceleration.

4–5. **A three-resistor network used two of them.** `_ordered_values` found all
   three and the extractor took `ohms[0]` and `ohms[1]`. Generalised to
   `R1..R4`, and a network larger than the table is refused rather than
   answered from a prefix — answering from a prefix *is* the bug.

6. **Scientific notation did not parse anywhere in the package.** The shared
   value scanners read `-?\d+(\.\d+)?`, so `6e24 kg` matched as **24 kg**.
   Astronomy is written this way; the fix is one shared `_NUMBER`.

7. **An altitude is not in the same unit as a radius.** `400 km` was added to
   `6.371e6 m` as the number 400, which gives the *surface* orbital speed to
   four significant figures — a wrong answer that looks entirely reasonable.
   The two now travel as separate params and are summed after `_to_si`.

An eighth was a missing answer rather than a wrong one, and is the most
architectural of the set. **`_CIRCUIT_CUE_RES` was dead in the pre-filter.** It
matches the SI symbols `V` and `A` case-sensitively — correctly, so that "3 a
piece" is not three amps — but `needs_symbolic` lowercased before testing the
same cues. Measured: "what is the electrical power for 12 V and 3 A" never
reached extraction in production, while the extractor test passed, because the
extractor re-ran the patterns against the original casing.

Two fixes were tried and rejected, and the reasons are in the comments. Plain
`IGNORECASE` fires on "3 a day and 2 a week" and "the 5 v 5 format beats 3 v 3"
(5 of 7 decoys). Requiring two *different* electrical symbols kills those (6/6
real, 0/7 decoys) but not "12 v cards and 3 a piece", which pairs a v with an a
exactly as a real question does. **The defect was the seam, not the pattern**:
the pre-filter was throwing away the casing the cue depends on.
`has_supported_physics_cue` now takes the text as written, and both sides share
one helper so they cannot disagree again.

## The twenty kinds

| Kind | Solved |
|---|---|
| `kinematics` | 1-D motion under gravity |
| `suvat` | constant acceleration, all four rearrangements |
| `projectile` | range, max height, **time of flight, impact speed, launch angle** |
| `force` | F = ma, resultants, components |
| `energy` | KE, PE, work, power |
| `momentum` | p = mv, impulse, 1-D collisions |
| `friction` | f = μN, incline acceleration, **μ from the slipping angle, minimum force** |
| `circular` | a_c, F_c, orbital period, **ω = v/r** |
| `spring` | F = kx, U, SHM and pendulum periods, **f = 1/T, v_max = Aω** |
| `circuit` | Ohm's law, power, **n-resistor networks, Q = It, E = Pt, C = Q/V, terminal voltage** |
| `torque` | τ = Fd, moment balance |
| **`waves`** | v = fλ, f = 1/T, Doppler |
| **`optics`** | thin lens, magnification, Snell, critical angle |
| **`thermal`** | Q = mcΔT, PV = nRT, efficiency |
| **`gravitation`** | F = GMm/r², orbital and escape velocity, surface gravity |
| **`fluids`** | P = F/A, ρgh, upthrust, density, continuity, flow rate |
| **`rotation`** | ω = θ/t, moment of inertia, L = Iω, rotational KE |
| **`magnetism`** | F = BIL, F = qvB, Φ = BA |
| **`materials`** | σ = F/A, ε = ΔL/L, E = σ/ε |
| **`modern`** | E = hf, de Broglie, half-life, E = mc² |

## What the new kinds refuse, and why

Round 1's rule decides these: *a wrong number in the verified block is worse
than no block at all*. Each is refused rather than guessed, and each has a test.

- **Optics sign conventions disagree between textbooks** for exactly the
  interesting cases. Only a converging lens forming a real image is solved. A
  student handed `+15 cm` where their book says `-15 cm` is worse off than with
  no answer.
- **27 °C and 27 K differ by a factor of eleven**, and "degrees" means an
  *angle* everywhere else in this package, so an absolute temperature with no
  scale is refused. A temperature *difference* is the same number on both
  scales and is the one reading allowed to stay loose.
- **Efficiency is two questions wearing one word.** W/Q_in from two energies is
  claimed; two temperatures is Carnot and is refused.
- **Doppler's sign is the answer**, so an unstated direction is refused. The
  assumed speed of sound is stated in the answer, because 340 and 343 are both
  taught.
- **The shape is the answer for a moment of inertia.** A "wheel", "flywheel" or
  "object" is not a shape, and answering one with the disc constant is a
  confidently wrong number.
- **A planet described but not named**, supplying only one of mass and radius,
  is refused. Finishing it with Earth's other number is defect 1 again, one
  layer up.
- **Buoyancy needs the submerged volume**; depth pressure is **gauge and says
  so**, because the absolute reading is 101 kPa higher.

## Three things that were not physics

- **"modulus" belongs to complex numbers first.** `SCHOOL_EXTRACTORS` run
  before `PHYSICS_EXTRACTORS`, so "the young modulus for a stress of 2e7 Pa"
  was read as |z|. The elastic moduli are now named explicitly there.
- **Stress and pressure are the same arithmetic.** σ = F/A and P = F/A differ
  by one word and nothing else, so `materials` runs before `fluids` and the cue
  sets are kept disjoint by vocabulary. One test pins each phrasing to its kind.
- **Pint's lowercase spellings are hostile**, and every extractor regex here is
  `IGNORECASE`, so they arrive. Measured: bare `pa` is a *petayear*, `t` a
  tonne, `c` the speed of light, `k` the Boltzmann constant. Without a
  `_PARAM_SI_DIMENSIONS` entry, "100 pa" for a pressure converts to **0.0032
  seconds** and the solve proceeds. `test_physics_param_dimensions.py` now
  walks every phrasing the suites verify and requires each param to declare a
  dimension — plus a check that every declared spec parses, so a typo cannot
  disable the guard.

## The prompt paragraph got shorter

`MATH_SOLVER_HINT` ships on every math turn and had **71 characters** of
headroom under a 2200-char cap. Naming nine more kinds by appending was not
possible. Tightening the existing wording paid for all of them: the clause now
names twenty kinds in 2163 characters, with 37 to spare and no cap raise.

`test_a_solved_topic_is_not_still_listed_as_unchecked` now loops over every
kind with a solver rather than checking the one word that caught it originally.
This round moved eight topics across; checking them by hand is how the next one
gets missed.

## Method note

The two baselines below were captured before any change and diffed after every
commit. Byte-identical was the bar, and it held for all six:

- 20 ordinary sentences → 4 reach the tool path (2 are genuinely maths, 2 are
  pre-existing false positives).
- 34 sentences chosen to collide with the *new* vocabulary — wave, lens, focus,
  pressure, flow, density, stress, strain, field, charge, half life, momentum,
  rotate, gravity, heat, efficiency — → 4, all pre-existing.

That second table earned its place twice. It caught "the half life of this meme
was 3 days" reaching the tool path the moment `half life` was added as a plain
substring cue, and it is why `wave`, `pressure`, `stress`, `density` and
`charge` are all co-occurrence cues rather than words.

## What is left

Genuinely not covered, and named in the prompt's caution sentence: relativity
beyond E = mc², quantum states beyond de Broglie, alternating current, entropy,
interference. Latent heat and Carnot efficiency are adjacent to shipped kinds
and refused explicitly. 2D collisions remain refused (P11).

**No mobile change in this round.** Every new kind answers with a number and
its substitution, or reuses a scene that already exists (the orbit for an
orbital velocity, a free body for an upthrust). No new `SimulationType`, so
`apps/mobile/lib/math/simulation.ts` — which duplicates the scene list and
silently drops an unknown `type` — needed no edit.
