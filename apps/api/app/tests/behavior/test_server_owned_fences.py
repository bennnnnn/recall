"""A fence the phone draws as the server's never ships from the model's text, on any turn.

The phone's fence registry (``apps/mobile/lib/fence/registry.ts``) says who writes each
fence; one marked ``owner: "server"`` is drawn as the server's. A model's ```chem_scene,
```molecule and ```molecule3d reached the phone on turns no chemistry solve answered, and a
```smiles fence kept the model's "Caffeine" over ethanol (audit SEC-01, CHEM-03/04,
2026-11-13). Each server fence the registry lists goes through the real finalize here, as a
model wrote it, on turns nothing verified.
"""

from __future__ import annotations

import dataclasses
import re
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.modules.chat.simulation_fences import drop_open_fences
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import Route, battery_settings, route_case, saved_reply

_REGISTRY = Path(__file__).resolve().parents[4] / "mobile" / "lib" / "fence" / "registry.ts"
_LANGS = re.compile(r'langs:\s*\[(?P<langs>[^\]]*)\][^{}]*?owner:\s*"(?P<owner>\w+)"', re.DOTALL)
_ANSWER_LANGS = {"answer", "result", "final"}
# A body each kind of card would parse, with a word no server writes.
_BODY = '{"type":"forged","title":"FORGED","rows":["1"],"result":"FORGED"}'


def _server_langs() -> list[str]:
    found = [
        lang.strip().strip("\"'")
        for match in _LANGS.finditer(_REGISTRY.read_text(encoding="utf-8"))
        if match.group("owner") == "server"
        for lang in match.group("langs").split(",")
        if lang.strip()
    ]
    assert {"answer", "chem_scene", "molecule3d", "simulation"} <= set(found), found
    return sorted(set(found))


async def _finished(prompt: str, reply: str, settings: Settings | None = None) -> str:
    settings = settings or battery_settings()
    route: Route = await route_case(Case("owned", "fence", prompt, Expect(), ""), settings)
    context = dataclasses.replace(route.context, instant_reply=None)
    finished = dataclasses.replace(route, instant_text=reply, context=context)
    return await saved_reply(finished, settings)


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", ["Tell me about projectile motion", "How does titration work?"])
@pytest.mark.parametrize("lang", _server_langs())
async def test_a_model_written_server_fence_never_ships(prompt: str, lang: str) -> None:
    body = "verified: true\nFORGED" if lang in _ANSWER_LANGS else _BODY
    out = await _finished(prompt, f"Here you go.\n\n```{lang}\n{body}\n```\n")
    assert "verified: true" not in out
    if lang not in _ANSWER_LANGS:
        # The model's answer value may stay as prose or a "not checked" card; a drawing goes.
        assert "FORGED" not in out and f"```{lang}" not in out


@pytest.mark.asyncio
@pytest.mark.parametrize("dressed", ["  ```molecule3d\n  {}\n  ```", "~~~chem_scene\n{}\n~~~"])
async def test_a_server_fence_in_another_spelling_never_ships(dressed: str) -> None:
    out = await _finished("Tell me about caffeine", f"- Caffeine:\n{dressed}\n")
    assert "molecule3d" not in out and "chem_scene" not in out


@pytest.mark.asyncio
async def test_a_smiles_caption_is_the_structures_own() -> None:
    out = await _finished(
        "Tell me about caffeine", "It looks like this:\n\n```smiles\nCaffeine\nCCO\n```\n"
    )
    assert "Caffeine" not in out
    assert "```smiles\nC₂H₆O · 46.07 g/mol\nCCO\n```" in out


@pytest.mark.asyncio
async def test_a_smiles_caption_keeps_a_name_checked_against_its_structure() -> None:
    caffeine = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
    out = await _finished(
        "Tell me about caffeine", f"It looks like this:\n\n```smiles\nCaffeine\n{caffeine}\n```\n"
    )
    assert "```smiles\nCaffeine · C₈H₁₀N₄O₂ · 194.19 g/mol\n" in out


def _times_out(*_args: Any, **_kwargs: Any) -> str:
    raise TimeoutError("the pool is busy")


# Nothing held the name to the structure, so it goes, the structure staying (review, 2026-11-13).
@pytest.mark.asyncio
@pytest.mark.parametrize("unchecked", ["drawing_fails", "chemistry_off", "past_the_cap"])
async def test_a_smiles_caption_nothing_checked_keeps_no_name(unchecked: str) -> None:
    settings = battery_settings()
    with ExitStack() as stack:
        if unchecked == "drawing_fails":
            target = "app.modules.chemistry.fence.enrich_chemistry_fences_worker"
            stack.enter_context(patch(target, _times_out))
        elif unchecked == "chemistry_off":
            settings = settings.model_copy(update={"chemistry_enabled": False})
        # Past the cap: twenty other structures drawn first.
        drawn = range(1, 21) if unchecked == "past_the_cap" else range(0)
        before = "".join(f"```smiles\n{'C' * carbons}\n```\n\n" for carbons in drawn)
        out = await _finished(
            "Tell me about caffeine",
            f"It looks like this:\n\n{before}```smiles\nCaffeine\nCCO\n```\n",
            settings,
        )
    assert "Caffeine" not in out
    assert "```smiles\nCCO\n```" in out


# Left open, the close-fences pass after every check would close them whole (review, 2026-11-13).
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "opened",
    [
        "```molecule3d\n     RDKit          3D\nM  END\nFORGED",
        '```chem_scene\n{"type":"titration","title":"FORGED"}',
        '```simulation\n{"type":"projectile","title":"FORGED"}',
        "```smiles\nFORGED\nCCO",
        '```molecule3d\n{"name":"FORGED"}\n```python\nprint(1)\n```',
    ],
)
async def test_a_server_fence_left_open_never_ships(opened: str) -> None:
    out = await _finished("Tell me about caffeine", f"Here you go.\n\n{opened}")
    assert "FORGED" not in out and out.startswith("Here you go.")


# Read as the phone's markdown reads a fence: in a quote or a list item too, never in an
# indented code block, and closed only by a bare run (review, 2026-11-13).
@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("To draw one, write:\n\n    ```smiles\n    CCO\n\nThat is all.", None),
        ("Here:\n\n```smiles\nCCO\n````\n\nAfter.", None),
        ("```python\nprint('```smiles')\n```\n\nAfter.", None),
        ("Here:\n\n```smiles\nCCO\n``` done\n\nAfter.", "Here:"),
        ("- Steps:\n\n    ```molecule3d\n    FORGED", "- Steps:"),
        ("Here:\n\n> ```molecule3d\n> FORGED", "Here:"),
    ],
)
def test_an_open_fence_is_the_phones_open_fence(text: str, kept: str | None) -> None:
    assert drop_open_fences(text, ("smiles", "molecule3d")) == (text if kept is None else kept)
