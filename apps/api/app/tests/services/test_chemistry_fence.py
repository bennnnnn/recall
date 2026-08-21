"""Chemistry fence enrichment — validate/enrich ```smiles fences."""

from __future__ import annotations

from app.services import chemistry_fence


def test_enrich_valid_smiles_canonicalizes() -> None:
    content = "```smiles\nOCC\n```"
    result = chemistry_fence.enrich_chemistry_fences(content)
    # OCC and CCO are both ethanol — should canonicalize to the same form.
    assert "```smiles" in result
    # Should not contain the original OCC
    assert "OCC" not in result


def test_enrich_valid_smiles_with_caption() -> None:
    content = "```smiles\nEthanol\nCCO\n```"
    result = chemistry_fence.enrich_chemistry_fences(content)
    assert "```smiles" in result
    assert "Ethanol" in result  # caption preserved


def test_enrich_invalid_smiles_stripped() -> None:
    content = "Here is a molecule:\n```smiles\nnot_a_smiles\n```\nDone."
    result = chemistry_fence.enrich_chemistry_fences(content)
    assert "```smiles" not in result
    assert "not_a_smiles" not in result
    assert "Done." in result


def test_enrich_multiple_smiles_fences() -> None:
    content = "```smiles\nCCO\n```\nand\n```smiles\nO=C=O\n```"
    result = chemistry_fence.enrich_chemistry_fences(content)
    assert result.count("```smiles") == 2


def test_enrich_chemistry_alias_fence() -> None:
    content = "```chemistry\nCCO\n```"
    result = chemistry_fence.enrich_chemistry_fences(content)
    # Should be normalized to ```smiles
    assert "```smiles" in result
    assert "```chemistry" not in result


def test_enrich_no_smiles_fences_unchanged() -> None:
    content = "Just some text without chemistry fences."
    result = chemistry_fence.enrich_chemistry_fences(content)
    assert result == content


def test_enrich_empty_fence_left_as_is() -> None:
    content = "```smiles\n\n```"
    result = chemistry_fence.enrich_chemistry_fences(content)
    # Empty fence body — no SMILES to validate, leave as-is
    assert result == content


def test_enrich_smiles_with_comment_lines() -> None:
    content = "```smiles\n# This is ethanol\nCCO\n```"
    result = chemistry_fence.enrich_chemistry_fences(content)
    assert "```smiles" in result
