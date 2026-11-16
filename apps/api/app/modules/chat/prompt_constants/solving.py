"""Safety rules shared by every deterministic subject solver."""

# A sentence around the working is held to the working: "Dropping the charges by a factor
# of 10^12 each cuts the force by 10^24" closed a reply whose working gave 2.16e-9 N from
# charges 10^12 and 10^6 times smaller, a factor of 10^18 (live, 2026-11-16). A number a
# remark works out in prose is the one no line of the working shows.
VERIFIED_SOLVE_SAFETY_HINT = (
    "Verified-solve safety: Never claim that an answer or procedure was verified "
    "unless this turn contains a matching [BEGIN VERIFIED ...] block. When a "
    "verified block is present, copy its canonical values and working exactly; "
    "do not independently recompute or override them. A sentence before or after the "
    "working states only numbers the question gives or the working shows: a comparison "
    "with another result (a factor, a ratio, a power of ten, a percentage) is a line of "
    "the working first, or it is said without a number."
)
