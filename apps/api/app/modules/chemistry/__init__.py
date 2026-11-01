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

# Seams the chat turn uses: question detection, follow-ups, prompt hints and post-stream
# fences; what the subject order (services/which_subject) reads of a line: the extracted
# intent, its text, a question's cues and a reaction's species; and ``subject``, chemistry as
# the subject registry (services/subject_registry) asks it, its verified block and its
# direct reply.
_MODULE_EXPORTS = (
    "context",
    "extract",
    "fence",
    "followup",
    "input_text",
    # The laws a model reader chooses from, and the intent its read binds to.
    "model_read",
    "reply_policy",
    "request",
    "shape_followup",
    "species",
    "subject",
)
