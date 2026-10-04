# Recall chemistry pipeline

Server-side typed extractors, pure solvers, RDKit, SymPy, and PubChem verify
chemistry. The mobile app renders the result; it does not solve chemistry on-device.

## Default product path

1. **Gate** (`request.py`) — recognizes supported calculations, chemistry-specific
   language, element questions, descriptors, and compound lookup. Generic phrases such
   as “how many” do not fire the chemistry path on their own, and neither do words that
   are chemistry only in company (`acid`, `base`, `boiling`, `nuclear`, `mole`,
   `compound`, `bond`): those need a second cue or a chemical formula. Symbols such as
   `Ka`, `pH`, and `Rf` match only with that capitalization (not “KB” or “Ph.D.”), and
   a scientist's name needs “law” (Charles's law, not Charles Darwin). “Chemistry” is
   the subject except in the idiom for getting along (“great chemistry”, “the chemistry
   between them”), and a half-life needs a number, a nuclide or a decay word (not a phone
   battery's). The gate reads
   the first and last 2,000 characters and its formula pattern is linear-time, so a
   long paste cannot stall the event loop. PubChem lookups on the turn path give up
   after 2 seconds.
2. **Extract** (`extract.py`) — converts a complete, unambiguous text problem to a
   validated `ChemistryIntent`. Missing or conflicting values return `None`; the
   extractor never invents a value. A number that carries a unit is converted, and a
   unit the registry cannot convert declines the problem instead of being read as the
   default unit. `1.8 × 10^-5` is read whole, never as `1.8`, by the shared
   `services/number_text` reader. One line is extracted once per turn: the result is
   cached per text and each caller gets its own copy. The templates in `extractors/`,
   one module per topic, read labelled phrasings ("Strong acid: 0.01 M HCl", "M1 = 2 M,
   V1 = 50 mL"). The first that returns an intent wins, so `registry.py` lists them in
   the order they run.
   A question in its own words ("What is the pH of 0.01 M HCl?") is read by the
   **binder** (`binding.py`) once every template has declined. It uses the law engine
   physics uses (`services/law_binding`):
   - the text is prepared first. A symbol whose case is its meaning is spelled out
     (`pH`, `Ka`, `E°`). Each substance named by formula or by name (`species_facts.py`:
     water, table salt, acetic acid…) becomes its role: strong or weak acid or base,
     conjugate salt, compound. Its digits are never read as numbers (the 2 of `Ca(OH)2`);
   - a law (`laws.py`) is tried only when the question names the substance it is
     about. A strong-acid pH needs exactly one strong acid;
   - the stated values fill the law's inputs by dimension (`given_units.py`: `M` is mol/L,
     `m` is mol/kg, `°C/m` a colligative constant) and by the words around them;
   - settings fill the rest:
     - the van 't Hoff factor of a named solute (glucose 1, NaCl 2);
     - the molar mass of the metal deposited, and the charge of its ion (`Cu2+`);
     - 25 °C for a Nernst cell with no temperature;
   - each input is converted to the unit its solver reads, so the solver is the same one
     a template reaches.

   Anything short of one law with one way to fill it declines: two strong acids, a
   weak acid without its Ka, a second time for one electrolysis. A titration in words
   pairs each volume with the solution it is "of" ("25 mL of 0.1 M HCl", "adding 10 mL of
   NaOH"); a volume no phrase ties to one solution declines. A binder fit is also a
   chemistry cue for the gate. A problem no reader knows goes to the model, unverified.
3. **Solve** (`solvers/`) — deterministic solvers, one module per topic (`amounts`,
   `stoichiometry`, `acid_base`, `titration`, `equilibrium`, `kinetics`, …), return
   `ChemistryResult` with Given, Find, named universal Formula, Substitution, and Answer
   fields; `solver.py` maps each operation to its solver. The catalog (`catalog.py`) is
   the one list of operations: `ChemistryIntent` refuses an operation it does not declare,
   or one it files under another kind.
4. **Respond** (`direct.py`) — a complete typed calculation returns the exact compact
   five-section answer without waiting for model prose. The value is a server
   ` ```answer ` fence whose first line is `notation: chemistry`, so the client
   draws it as text instead of LaTeX. Image questions remain on the vision/model
   path because OCR text was not the typed extractor input. Substitution is the
   formula with the numbers put in, never a repeat of the answer.
5. **Finalize** (`fence.py`) — a verified result drops model answer, scene, and
   structure fences and appends the solver's copies. An unclosed model fence is closed
   first, so it cannot swallow the fences the server appends. Closed `smiles` /
   `chemistry` fences are then validated. The server appends `molecule3d` SDF for the
   first two valid structures, at most 120 heavy atoms each, so the client never has to
   drop an oversize block.
6. **Render** — smiles-drawer retains chemically aware 2D layout inside its sandboxed
   WebView. The interactive 3D molecule projection uses a native Skia canvas, with the
   same projected SVG scene as a safe Expo Go / stale-client fallback. Adjacent 2D and
   3D fences collapse into one molecule card.

```mermaid
flowchart LR
  message[User message] --> gate[Chemistry gate]
  gate --> extract[Typed extraction]
  extract -->|complete| solve[Pure solver]
  solve --> direct[Given / Find / Formula / Substitution / Answer]
  extract -->|incomplete| model[Model explanation]
  gate -->|compound| pubchem[PubChem context]
  model --> enrich[SMILES validation + 3D enrichment]
  pubchem --> model
  enrich --> mobile[2D smiles-drawer + native-first Skia 3D]
```

## Formula vs SMILES (`molar_mass`)

Hill formulas (`CO`, `C`, `H2O`, hydrates such as `CuSO4.5H2O`) are summed from
the element table (`elements.py`), so RDKit cannot saturate them into hydrides. Organic
strings that use SMILES-only syntax (`=`, `#`, `@`, ring-closure digits such as
`C1CCCCC1`), or strings such as `CCO`, use RDKit. `NaCl` stays a formula. Molar mass is shown to two decimals (glucose 180.16 g/mol).

## Shared chemistry primitives

Verified operations share one species model instead of one-off formula patches.

| Primitive | What it carries |
|---|---|
| Element | all 118 elements: atomic number, symbol, name, atomic mass, and, where a standard value exists, group, period, electronegativity, common oxidation states, and electron configuration. An element with no standard atomic weight (Tc, Pm, and every element from Po on except Th, Pa, and U) carries the mass number of a long-lived isotope, marked `*` in the source table. Helium, neon, argon, and radon omit electronegativity; krypton and xenon have one. |
| `ChemicalSpecies` | formula, elemental composition, ionic charge, and optional phase (`s`, `l`, `g`, `aq`) |
| `ChemicalReaction` | reactant and product terms, each a species plus a coefficient |
| Quantity | school units normalized through the shared Pint registry (`25 °C` → 298.15 K, mmHg/kPa/bar → atm, mL → L) by the extractors for gas states, solution volumes, and dilution, before a solver sees them. mM, µM, nM, kcal, g/L and g/mL are read by the readers that convert units (the binder and Michaelis–Menten): the labelled templates never see them, since `M1 = 5 mM` would read as 5 M. An unsupported unit declines |

Balancing builds a SymPy nullspace over atoms and, when any species is charged, over charge. It recounts both and refuses an underdetermined or non-positive coefficient set. Electrons are a species with charge −1 and no atoms. A glued `+` or `−` is charge (`Fe2+`, `MnO4-`, `SO4^2-`); `H2 + O2` stays a term separator. A polyatomic ion whose charge follows a digit (`Cr2O72-`) is ambiguous, so it must be written with a caret (`Cr2O7^2-`) or the equation is refused rather than balanced wrongly. Reaction arrows are `->`, `→`, `=>`, `-->`, `⟶`, `<=>`, `⇌`, `⇋`, `<->`, and `↔`, read longest first.

Pure solids and liquids are omitted from `Kc`, `Kp`, and solubility products only when the phase is written on the species. An unlabeled formula still counts, so a homogeneous concentration equilibrium is unchanged.

## Verified calculation coverage

| Group | Operations |
|---|---|
| Equations | atom-and-charge balancing, including ionic and redox half-equations that already contain `e-`; a written redox pair when the question asks to balance it or names a half-reaction, in acidic or basic solution, adding `H2O`, `H+` or `OH-`, and `e-`. The pair itself may be water, `H+`, or `OH-` (`O2 -> H2O`, `H+ -> H2`), including a one-element ion whose oxidation number is a fraction (`O2 -> O2-`). A pair whose oxidation numbers do not change stays with the ordinary balancer. `H2O -> H2` declines: cancelling the written water would leave a different pair. An ambiguous oxidation state such as FeS declines, and a multi-species equation is not completed into a full redox reaction |
| Amounts | molar mass, mass ↔ moles, moles ↔ particles, particles → mass, percent composition, the mass of an element in a sample (`10.0 g` of H2O holds `8.88 g` of O), average atomic mass from isotope abundances (stated isotope masses, or the isotope table in `isotopes.py`, never the mass numbers), percent yield, atom economy of one named product in an equation whose written coefficients already conserve atoms (a common multiple counts; the printed formula includes each coefficient), empirical formula, molecular formula, combustion analysis of a C/H/O compound (or carbon and hydrogen only) from the sample mass and the CO2 and H2O masses. Another element declines, and so do masses that do not close |
| Stoichiometry | mole ratios; grams, moles, or particles through the balanced ratio to grams, moles, or particles; solution volume/molarity → product; gas volume at the same P and T; limiting reagent from masses or solution volumes, with theoretical yield and excess reactant |
| Solutions | molarity, mass from molarity, dilution (including the stock volume: `6.0 M` to make `500 mL` of `1.5 M`), molality (also from the solute and solvent masses), mass percent, mole fraction, parts per million and parts per billion (mass of solute over mass of solution, from none of the solution up to all of it), volume percent, mass/volume percent (grams of solute per 100 mL of solution), boiling-point elevation, freezing-point depression, osmotic pressure, Raoult's law for one component (`P = X P°`), and the total vapor pressure of an ideal binary solution (`P = X_A P_A° + X_B P_B°`) |
| Acid–base | pH from `[H+]`, pOH, or a strong monoprotic acid / strong base concentration; weak-acid and weak-base quadratics; `Ka`/`Kb`/`Kw` and `pKa`/`pKb`; Henderson–Hasselbalch; buffer after adding strong acid or base; strong titration, weak acid–strong base, and weak base–strong acid regions; a neutralization's unknown concentration with the mole ratio (H2SO4 neutralizes two NaOH); percent ionization; first dissociation of a polyprotic acid. An amphiprotic pH is `(pKa1 + pKa2) / 2` when both constants are stated. A stated concentration has to be high enough for that average (well above `Ka1` and `Kw/Ka2`); a very dilute salt declines. `[A2-]` is `Ka2` when that concentration is asked and the second dissociation is weak (`Ka2` below `10^-3`, and well below a stated acid concentration). A charge-balance speciation is not solved. A titration in words with a dihydroxide base (Ca(OH)2) declines |
| Gases | Dalton, including partial pressures listed in words; gas density and molar mass from density (`d = PM/RT`, M from the named gas); Graham's law for two named gases, or for a rate or molar mass from the other three (`r1 =`, `M1 =`); Henry's law `C = kH × P` for any one of the three; mole-fraction partial pressure; gas collected over water (water vapor pressure is interpolated between the tabulated points, log-linear in 1/T, from 0 to 100 °C). The ideal gas law, Boyle, Charles and the combined law are physics' (see **Shared laws**) |
| Thermochemistry | the heat of a reaction amount `q = nΔH`, calorimetry `q_rxn = −q_cal`, Hess's law, formation enthalpy, bond enthalpy, `ΔG = ΔH − TΔS`, and two-point Clausius–Clapeyron for ΔHvap or a vapor pressure. `q = mcΔT`, latent heat and a metal's specific heat by calorimetry are physics' |
| Equilibrium | homogeneous `Kc` and `Qc`; phase-aware `Kc`/`Kp`; `Kc` ↔ `Kp`; quadratic ICE solutions, asked as "the equilibrium concentrations" with `[H2] = [I2] = 1.0 M` read as both; `Ksp`, molar solubility (a salt named by its formula gets its dissolution equation from its cation and a known anion: `Fe(OH)3` is Fe3+ and 3 OH-), common-ion solubility, and `Qsp` versus `Ksp`; two-point van 't Hoff for `K2` or `ΔH°`; `ΔG° = −RT ln K` for either side |
| Kinetics | zero-, first-, and second-order integrated laws and half-lives; a first-order `k` from its half-life, per the half-life's time unit; integer order from two experiments; one-temperature and two-temperature Arrhenius |
| Electrochemistry | `ΔG° = −nFE°`, Nernst potential, Faraday electrolysis mass and time (a metal named without its ion takes the galvanic table's ion, Cu2+), `E°cell = E°cathode − E°anode`, and a galvanic cell from the built-in reduction table |
| Nuclear | one-missing-product nuclear equations (alpha, beta, positron, electron capture, written with the captured electron: `7Be + e- → 7Li`) that conserve both mass number and charge, and mass defect / binding energy when the nuclear mass in u is supplied. A half-life amount, decay constant and activity are physics' |
| Spectroscopy | Beer–Lambert for any one of absorbance, molar absorptivity, path length, or concentration; IR and 1H NMR ranges for recognized functional groups; a peak lists every group whose range contains it; the n+1 rule when the neighbor count is stated; molecular ion is the monoisotopic mass with nominal m/z and the Cl/Br M+2 pattern |
| Structure | the ground-state electron configuration of a neutral atom from the element table (exceptions such as Cu kept; an ion declines), school oxidation states, formal charge, and single-center VSEPR. The molecular angle is separate from the ideal electron-domain angle. With several different non-hydrogen atoms and no hydrogen, the center is the least electronegative one (`SOCl2`, `POCl3`, `XeOF4`); with hydrogen present it is not guessed (`HOCl`). A single carbon is the center of an HCN-style formula. Identical terminals with unequal bonds are counted as resonance forms |
| Organic | RDKit functional groups matched atom by atom (including nitro, thiol, acyl halide, anhydride, and aryl halide), CIP labels from RDKit's CIP labeller (`atom 2 (C): S`, `C2=C3: E`), and isomer class (identical, constitutional, or stereo). A PubChem `IUPACName` is verified only when that property is returned. Five one-product reactions (HBr addition, bromine addition, acid hydration, primary-halide hydroxide substitution, esterification) return one SMILES; an addition across an unsymmetrical alkene that could give two products is declined |
| Inorganic | oxidation state, coordination number, and additive name for the built-in ligand table. Crystal field for a first-row metal: coordination number 6 is octahedral, and 4 needs a stated tetrahedral or square planar geometry. An octahedral d4–d7 complex is high-spin when every ligand is weak-field (halide, water, hydroxide) and low-spin when every ligand is strong-field (CN−, CO); NH3, en, and NO2− decide it only for Co(III) (low-spin). Any other d4–d7 ligand set is declined, because its spin state depends on the metal. The answer includes unpaired electrons and `μ = √(n(n+2))` |
| Analytical | linear calibration, gravimetric factor, one-point standard addition, sample standard deviation, standard error, percent error, relative uncertainty of a product or quotient, and chromatography `Rf` |
| Biochemistry | Michaelis–Menten for any one of `v`, `Vmax`, `Km`, and `[S]`, named or recognized by its `Vmax` and `Km`, in the units they are written in (`10 μmol/min`, `2.0 mM`) |

### Shared laws

A law both subjects teach has one implementation, in physics' catalog: the ideal gas law,
Boyle, Charles, Gay-Lussac and the combined law; `Q = mcΔT`; a half-life amount, a decay
constant and an activity. A chemistry question routes to physics for them
(`services/subject_solving.detect_subject`) and reads its answer in its own units:

- a gas stated in litres or atmospheres gives a volume in L and a pressure in atm, not m³
  and Pa ("2 mol at 300 K and 1 atm" occupies 49.2 L). A gas stated in m³ or Pa keeps SI;
- a rate from a half-life in years, days or minutes is per that unit (1.21 × 10⁻⁴ 1/yr);
- the subscripted states a chemistry class writes are read: `P1 = 2 atm, V1 = 3 L, V2 = 6 L,
  find P2`.

- a latent heat per gram is read as a chemistry class labels it (`ΔHfus = 334 J/g`);
- a hot object dropped into water gives its specific heat by calorimetry, with water's c as
  the setting, and in grams and °C a specific heat is per gram and degree (`0.558 J/(g·°C)`,
  not `558 J/(kg·K)`).

Every converted answer shows the conversion as its last substitution row. Routing also runs
the other way: a closed chemistry calculation (a mass percent, a molality, a cell potential)
is chemistry's before physics can claim its numbers. A gas law with no unit, or a Celsius
written as a bare `C` (a coulomb to physics), declines rather than guess.

Element lookup (including atomic number and configuration), molecular descriptors, and PubChem compound lookup are also verified context sources. A result is labelled verified only after extraction and solver success.

The galvanic table is the common school set Li, K, Ba, Ca, Na, Mg, Al, Mn, Zn, Cr, Fe, Cd, Co, Ni, Sn, Pb, H, Cu, Ag, Hg, and Au. Polyprotic pH uses the first dissociation only. An amphiprotic intermediate uses both pKa values when any stated concentration is high enough for that average, and `[A2-]` is `Ka2` only when that concentration is asked and it stays well below the acid. Rate-law fitting needs the two experiments to change one concentration. VSEPR refuses a chain or a second central atom (`H2O2`, acetic acid), a formula whose center is not determined (`HOCl`), transition metals, and a Lewis structure whose formal charges do not sum to the charge. A bent or pyramidal angle is 104.5° or 107° only for a second-period center with hydrogen terminals (water, ammonia); any other lone-pair shape is reported as less than the ideal angle, not as one invented measurement (H2S is about 92°, not 104.5°). Sulfuric acid is refused as a strong monoprotic acid. Oxidation states that the school rules do not decide, such as `FeS`, are refused.

## Notation and numbers

Solvers, the model prompt, and `canonical_answer` write ASCII: `H2SO4`, `Fe2+`,
`SO4^2-`, `[H+]`, `10^-4`, `->`. `notation.typeset` re-encodes that text for display
only (`H₂SO₄`, `Fe²⁺`, `SO₄²⁻`, `10⁻⁴`, `→`, and a true minus sign) in the direct reply,
the answer fence, `chem_scene` strings, and the molecule caption. It changes characters
and nothing else, and a result marked `verbatim` (organic and SMILES spectroscopy
results, IUPAC names) is never typeset. The model is told to write species with
Unicode sub- and superscripts and `→` / `⇌` arrows, not LaTeX.

A verified answer is laid out as a textbook worked solution (`direct.py`): **Given**,
**Find**, **Formula**, **Substitution**, **Answer**. An operation that is a procedure rather
than an equation (balancing, a correlation table, a structure match, an electron
configuration: `catalog.METHODS`) shows its rule under **Method** and checks it under
**Working**. Substitutions carry units (`n = 36 g / 18.015 g/mol`, `c = 0.5 mol / 2.0 L`),
and a unit change is a row of its own (`ΔG° = -2.1 × 10^5 J/mol = -2.1 × 10^2 kJ/mol`). A
given an extractor converted is shown as typed, then as used: `V = 500 mL = 0.500 L`,
`ΔS = -200 J/(mol·K) = -0.200 kJ/(mol·K)`, `T = 37 °C = 310.15 K`, `t = 1 h = 3600 s`. The
converted value keeps the typed figures without rounding away the conversion's own digits,
and a value two typed numbers could explain (1800 s from `30 min`, or from `0.50 × 3600`)
is not echoed as either. The headings are the server's text, like physics' and math's.

Numbers keep the precision the question was written in (`sig_figs.py`). Extraction
records how each given was typed, and the solve formats every number from that record:

- **Answers** take the fewest significant figures among the measured givens, kept between
  2 and 4: `4 g` of H₂ makes `36 g` of water, `4.000 g` makes `35.74 g`. A count (an electron
  number, a van 't Hoff factor, a Hess's-law multiplier) never limits the answer, and a
  Celsius reading counts the figures of its kelvin value (`25 °C` is `298 K`, three).
- **Trailing zeros are significant**: `pH = 3.00`, `n = 2.0 mol`. The model prompt tells the
  model to copy each verified number exactly, neither adding nor dropping a zero.
- **Typed values are echoed as typed**: `E° = 1.10 V` stays `1.10 V`, `Kc = 0.02370` keeps its zero.
- **A pH, pOH or pK** is a logarithm, so it has as many decimals as its data have
  figures: `[H+] = 2.5 × 10^-4` gives `pH = 3.60`. A concentration from a typed pH has as
  many figures as the pH has decimals (`pH = 4.50` gives `3.2 × 10^-5`).
- **A sum of givens** (cell potential, Hess's law, formation or bond enthalpy, Dalton) keeps
  the fewest decimal places instead: `0.34 − (−0.76) = 1.10 V`, `2(−92.3) = −184.6 kJ/mol`.
  A galvanic-table potential is a hundredth of a volt.
- **A whole number whose digits rounding replaced with zeros** is written in powers of
  ten: `1780` to two figures is `1.8 × 10^3`, since `1800` would read as measured. Zeros
  that are the number's own digits stay plain: `110 g`, `200 mL`.
- **Molar masses** stay at full precision inside the arithmetic. A working row shows them
  to the table's three decimals (`18.015`), and only a molar-mass answer rounds to two
  (`98.07 g/mol`). Rounding first moved answers: 4 g of H₂ gave 35.68 g of water, not 35.74.
- A physical constant is a CODATA value from the shared Pint registry (`services/units.constant`,
  pinned by a test) and is shown to 5 figures (`R = 0.08206`). Intermediate rows show
  the answer's figures while the arithmetic keeps full precision.

## Teaching scenes

A complete balance, stoichiometry chain, VSEPR, titration, ICE, or galvanic-cell
answer appends one server-owned `chem_scene` fence. The phone only draws that
JSON: card titles, column headings, and labels come from the app's i18n strings, the
atom tally and ICE table are drawn as tables, and the web shows a text summary. The
model prompt names `answer`, `smiles`, and `chem_scene` so the model does not emit them.

`docs/fixtures/chemistry_replies.json` holds real server replies. The server test
proves the server still writes exactly those replies, and the mobile and web tests read
the same file to prove each client draws them (regenerate with
`UPDATE_CHEMISTRY_FIXTURE=1`).

## Deliberate model-only boundary

The model may explain work outside the table, but must not call it verified. This
includes curved-arrow reaction mechanisms, biochemical pathways, chromatogram
images, a structure guessed from one spectral peak, and a nuclear mass that was
not supplied. Coordination number 4 is drawn as tetrahedral, not square planar.

## Key files

| Layer | Path |
|---|---|
| Intent schema | `apps/api/app/models/schemas/chemistry/intent.py` |
| Gate / compound parsing | `apps/api/app/modules/chemistry/request.py` |
| Text extraction | `apps/api/app/modules/chemistry/extract.py` (driver), `registry.py` (order), `extractors/<topic>.py` |
| Binder (questions in their own words) | `binding.py`, `laws.py`, `species_facts.py`, `given_units.py`; engine in `apps/api/app/services/law_binding/` |
| Typed solver dispatcher | `apps/api/app/modules/chemistry/solvers/solver.py` |
| Formula catalog | `apps/api/app/modules/chemistry/catalog.py` |
| Teaching scenes | `apps/api/app/modules/chemistry/scene.py` |
| Topic solvers | `apps/api/app/modules/chemistry/solvers/<topic>.py` |
| Verified block / direct reply | `apps/api/app/modules/chemistry/block.py`, `direct.py` |
| Turn integration | `apps/api/app/modules/chemistry/context.py` |
| Balance / formula primitives | `apps/api/app/modules/chemistry/equations.py`, `stoichiometry.py` |
| Species, elements, units | `species.py`, `formula.py`, `elements.py`, `quantity.py` |
| Notation / number format | `notation.py`, `sig_figs.py`, `solvers/types.py`, `solvers/common_chem.py`, `solvers/constants.py`, `solvers/params.py` |
| Structure / organic / nuclear | `structure.py`, `lewis.py`, `organic.py`, `coordination.py`, `nuclear.py` |
| SMILES / 3D / post-stream | `apps/api/app/modules/chemistry/smiles.py`, `fence.py` |
| PubChem | `apps/api/app/gateways/pubchem_gateway.py` |
| Mobile scan errors | `apps/mobile/lib/scanner/scanReadError.ts` (every subject) |
| Mobile parse / render | `apps/mobile/lib/chemistry/` (fence parsing, `smilesDrawerHtml.ts`, `molecule3dLayout.ts`), `apps/mobile/components/rich/` |
| Web render | `apps/web/src/lib/chemScene.ts`, `assistantMarkdown.ts` |
| Client contract | `docs/fixtures/chemistry_replies.json` |
| QA corpus | `apps/api/app/tests/modules/chemistry/corpus.py`, `corpus_physical.py` (hand-worked school questions; no verified answer may be wrong, coverage floor only rises) |

Feature flag: `chemistry_enabled` (on by default).
