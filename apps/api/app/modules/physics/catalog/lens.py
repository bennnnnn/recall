"""The thin-lens and mirror equation and the magnification it gives, as one pair.

The image's distance one law works out is the distance magnification reads, so "where is
the image and how big is it" is answered in two steps (``law_binding.chain``). Thin lenses
in contact add their powers.
"""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, formula, var
from app.services.law_binding.words import COMBINED_RESULT

# One object distance, image distance and focal length for the lens laws: the image's
# distance a law works out is the one magnification reads (``law_binding.chain``). The
# image distance is a given only when the words name it.
# The object's distance, however it is said: "an object 30 cm away", "a candle 40 cm from a
# lens", "placed 25 cm in front of it" (the image-height law reads it the same way).
_D_OBJ = var(
    "d_obj",
    "d_o",
    "meter",
    words=("object", "from a", "from the", "in front", "away", "placed"),
)
_D_IMG = var("d_img", "d_i", "meter", words=("image",), needs_words=True)
_FOCAL = var("focal", "f", "meter", words=("focal",))
# A diverging lens or a convex mirror has a negative focal length, a sign the question
# has not stated; inside F the image is virtual and its distance's sign is a convention.
_NOT_A_REAL_IMAGE = ("diverging", "virtual", "signed", "telescope", "microscope", "radius")

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "image_distance",
        "optics",
        "Thin-lens and mirror equation",
        "d_i",
        base_latex="\\frac{1}{f} = \\frac{1}{d_o} + \\frac{1}{d_i}",
        variables=(
            _D_OBJ,
            _FOCAL,
            _D_IMG,
            # Not in the formula: a lens and a concave mirror share it, and
            # only the ray diagram tells them apart.
            var("mirror", "mirror", dimensionless=True, visible=False),
        ),
        binding=Binding(
            asks=(
                "where is the image",
                "where will the image",
                "where does the image",
                "image distance",
                "distance of the image",
            ),
            result=("meter",),
            inputs=(frozenset({"d_obj", "focal"}),),
            cues=("lens", "mirror"),
            excludes=_NOT_A_REAL_IMAGE,
            # Outside F the image is real and its distance positive; inside, it is not chained.
            requires=("d_obj - focal",),
            nonnegative=True,
        ),
    ),
    formula(
        "magnification_distances",
        "optics",
        "Magnification equation",
        "m",
        base_latex=r"m = -\frac{d_i}{d_o}",
        assumptions=("real distances are positive; a negative m is an inverted image",),
        expression="-d_img/d_obj",
        variables=(_D_IMG, _D_OBJ),
        binding=Binding(
            asks=("magnification", "how big", "image size", "size of the image"),
            result=("dimensionless",),
            inputs=(frozenset({"d_img", "d_obj"}),),
            # A virtual, erect or "signed" image's distance carries the other sign, and any place
            # named may be the image's (optic_elements._PLACE). Heights are not d_o and d_i.
            excludes=(
                *("virtual", "erect", "upright", "behind", "beyond", "side", "in front", "left of"),
                *("right of", "diverging", "signed", "telescope", "eyepiece", "objective"),
                *("height", "tall", "high"),
            ),
        ),
    ),
    formula(
        "lens_power_sum",
        "optics",
        "Thin lenses in contact",
        "P",
        base_latex=r"P = P_1 + P_2",
        assumptions=("the lenses are thin and in contact",),
        expression="p1+p2",
        variables=(
            var("p1", "P_1", "1 / meter"),
            var("p2", "P_2", "1 / meter"),
        ),
        binding=Binding(
            asks=("power", "lens power", "total power"),
            result=("1 / meter",),
            inputs=(frozenset({"p1", "p2"}),),
            cues=("in contact",),
            interchangeable=("p1", "p2"),
            excludes=("telescope", "diverging"),  # a concave lens's power is negative
            # "a total power of 3 D" is the sum, not a lens: the other lens is P - P₁.
            result_labels=COMBINED_RESULT,
            nonnegative=True,
        ),
    ),
)
