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
from pathlib import Path

import pytest

from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import Route, route_case, saved_reply

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


async def _finished(prompt: str, reply: str) -> str:
    route: Route = await route_case(Case("owned", "fence", prompt, Expect(), ""))
    context = dataclasses.replace(route.context, instant_reply=None)
    return await saved_reply(dataclasses.replace(route, instant_text=reply, context=context))


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
