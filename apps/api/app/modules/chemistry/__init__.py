"""Chemistry service package and stable public API."""

from app.modules.chemistry.equations import (
    balance_equation,
)
from app.modules.chemistry.smiles import (
    MoleculeProperties,
    compute_descriptors,
    generate_3d_coordinates,
    validate_smiles,
)
from app.modules.chemistry.solvers import solve_chemistry
from app.modules.chemistry.stoichiometry import (
    limiting_reagent,
    molar_mass,
    stoichiometry,
)

__all__ = [
    "MoleculeProperties",
    "balance_equation",
    "compute_descriptors",
    "generate_3d_coordinates",
    "limiting_reagent",
    "molar_mass",
    "solve_chemistry",
    "stoichiometry",
    "validate_smiles",
]

# Seams the chat turn uses: question detection, follow-ups, and post-stream fences; and
# what the subject dispatcher (services/subject_solving) reads: the reading, the
# extracted intent, the verified block and the direct reply.
_MODULE_EXPORTS = (
    "block",
    "context",
    "direct",
    "extract",
    "fence",
    "followup",
    "input_text",
    "reading",
    "reply_policy",
    "request",
    "shape_followup",
    "species",
)
