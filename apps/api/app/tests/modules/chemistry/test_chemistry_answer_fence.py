"""Verified chemistry answers stay on the chemistry fence contract."""

from __future__ import annotations

import json

from app.models.schemas.chemistry.scene import dump_scene
from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.direct import format_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.fence import validate_chemistry_fences
from app.modules.chemistry.notation import typeset_json
from app.services.chat.presentation import present_assistant_markdown


def _verified(question: str):
    intent = extract_chemistry_intent(question)
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    return verified


def test_direct_reply_is_idempotent_under_chemistry_finalization() -> None:
    verified = _verified("Find pH when [H+] = 0.001")
    reply = format_direct_chemistry_reply(verified)
    assert validate_chemistry_fences(reply, verified=verified) == reply


def test_model_answer_and_structure_are_replaced_by_the_solver() -> None:
    verified = _verified("Find pH when [H+] = 0.001")
    invented = "\n".join(
        [
            "The pH is 4.",
            "",
            "```answer",
            "4",
            "```",
            "",
            "```smiles",
            "CCO",
            "```",
            "",
            "```chem_scene",
            '{"type":"balance"}',
            "```",
        ]
    )
    finalized = validate_chemistry_fences(invented, verified=verified)
    assert finalized.count("```answer") == 1
    assert "notation: chemistry\npH = 3" in finalized
    assert "```smiles" not in finalized
    assert "```chem_scene" not in finalized
    assert "The pH is 4." in finalized


def test_solver_scene_survives_and_is_not_duplicated() -> None:
    verified = _verified("VSEPR of H2O")
    reply = format_direct_chemistry_reply(verified)
    scene = verified.result.scene
    assert scene is not None
    payload = json.dumps(typeset_json(dump_scene(scene)), ensure_ascii=False)
    fence = f"```chem_scene\n{payload}\n```"
    assert reply.count("```chem_scene") == 1
    assert reply.rstrip().endswith(fence)
    assert validate_chemistry_fences(reply, verified=verified) == reply


def test_answer_fence_body_is_not_rewritten_as_a_calculation_chain() -> None:
    fence = "```answer\nnotation: chemistry\nM(H2O) = 18.015 g/mol = 18 g/mol\n```"
    assert present_assistant_markdown(fence) == fence


def test_unverified_text_is_left_unchanged() -> None:
    raw = "```answer\n4\n```"
    assert validate_chemistry_fences(raw, verified=None) == raw
