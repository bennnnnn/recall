"""Every SI prefix on every SI unit the physics givens read, as a symbol and as a word.

The unit table listed prefixed spellings one at a time, so a prefix nobody had met was no
unit: "take the charges as 3.0 pC and 2.0 μC" read the 3.0 as a bare number and the
follow-up that changed both charges reached no solver (live, 2026-11-16), while nC, μC and
pF were read. Every prefix on every base is written here once, and the table's own
spellings are laid over them (``given_units``). The extractors read them too: a reader's
unit pattern takes every prefixed spelling of a base it reads (``with_prefixes``).

Left out, by what they are after a number in a school question: "pm" a clock time, "pH"
acidity, "pV" the gas law's product, "kT" a thermal energy, "Mg" magnesium, "Ms" a title,
"us" a word, "Gs" g-forces ("pulls 5 Gs"), "GA" a wire gauge ("12 GA copper wire"), "GT" a
car, "Gm" the gravitational parameter, and "GF", "GH" and "GC", which no question writes
for a gigafarad, a gigahenry or a gigacoulomb but other words do. Peta (P) is left out too:
"PC", "PA", "PT" and "PH" are other things, and no school question writes a petajoule. Centi
goes only on the metre, the gram and the litre, as SI writes it. The G forms that stay are
those a question writes: GW, GJ, GHz, GeV and GPa (listed), GΩ, GL, Gg, GN and GV.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.services.law_binding.units import SI_PREFIXES

# Each base SI symbol a question writes after a number, with its Pint name.
_BASE_SYMBOLS: dict[str, str] = {
    "m": "meter",
    "g": "gram",
    "s": "second",
    "L": "liter",
    "N": "newton",
    "J": "joule",
    "W": "watt",
    "A": "ampere",
    "V": "volt",
    "C": "coulomb",
    "F": "farad",
    "H": "henry",
    "T": "tesla",
    "Ω": "ohm",
    "Pa": "pascal",
    "Hz": "hertz",
    "eV": "electron_volt",
    "Wb": "weber",
    "K": "kelvin",
}
# The same bases spelled out, as a question writes them (read without case), each with its
# plural.
_BASE_WORDS: dict[str, tuple[str, str]] = {
    "meter": ("meter", "meters"),
    "metre": ("meter", "metres"),
    "gram": ("gram", "grams"),
    "second": ("second", "seconds"),
    "liter": ("liter", "liters"),
    "litre": ("liter", "litres"),
    "newton": ("newton", "newtons"),
    "joule": ("joule", "joules"),
    "watt": ("watt", "watts"),
    "ampere": ("ampere", "amperes"),
    "amp": ("ampere", "amps"),
    "volt": ("volt", "volts"),
    "coulomb": ("coulomb", "coulombs"),
    "farad": ("farad", "farads"),
    "henry": ("henry", "henries"),
    "tesla": ("tesla", "teslas"),
    "ohm": ("ohm", "ohms"),
    "pascal": ("pascal", "pascals"),
    "hertz": ("hertz", "hertz"),
    "weber": ("weber", "webers"),
    "kelvin": ("kelvin", "kelvins"),
}
_CENTI_ON = frozenset({"m", "g", "L", "meter", "gram", "liter"})
_LEFT_OUT = frozenset(
    {"pm", "pH", "pV", "kT", "Mg", "Ms", "us", "Gs", "GA", "GT", "Gm", "GF", "GH", "GC"}
    # A temperature takes milli-, micro- and nano- ("250 mK"); "pK" is an acid's constant.
    | {"pK", "kK", "MK", "GK"}
)
_PETA = "P"


def _prefixes(base: str) -> list[tuple[str, str]]:
    """(symbol, Pint name) of each prefix this base takes."""
    return [
        (symbol, name)
        for symbol, (name, _power) in SI_PREFIXES.items()
        if symbol != _PETA and (name != "centi" or base in _CENTI_ON)
    ]


def prefixed_symbols(listed: Mapping[str, str]) -> dict[str, str]:
    """ "pC" → "picocoulomb", "kΩ" → "kiloohm": each prefix on each base symbol, but for a
    spelling whose prefix in the other case the table ``listed`` already reads. An extractor
    that matched "MN" without case may have read the listed "mN" (or "mPa" the listed
    "MPa"): the twin stays unread, so such a reading is refused, never guessed (review
    2026-11-07)."""
    out: dict[str, str] = {}
    for base, name in _BASE_SYMBOLS.items():
        for symbol, prefix in _prefixes(base):
            spelling = symbol + base
            twin = symbol.swapcase() + base
            if spelling in _LEFT_OUT or (twin != spelling and twin in listed):
                continue
            out[spelling] = prefix + name
    return out


def prefixed_words() -> dict[str, str]:
    """ "picocoulombs" → "picocoulomb": each prefix's name on each base word, lowercase."""
    out: dict[str, str] = {}
    for word, (name, plural) in _BASE_WORDS.items():
        for _symbol, prefix in _prefixes(name):
            out[prefix + word] = prefix + name
            out[prefix + plural] = prefix + name
    return out
