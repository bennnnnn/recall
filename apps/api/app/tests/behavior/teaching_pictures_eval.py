"""Measure the pictures drawn for questions that ask to see none.

A script, not a test: it calls the real models through the gateway (and PubChem for
chemistry), so it needs an OpenRouter key in the environment, and nothing else.

    python -m app.tests.behavior.teaching_pictures_eval --runs 3

Every question of ``teaching_pictures_corpus.json`` asks to see no picture and is labelled
with whether one helps teach it. Maths runs the figure read told the user did not ask
(``math.figure.read``) and builds the figure, checked against the question; chemistry runs
the compound read and draws the compound's structure (``chemistry.figure``). Each run prints
the unwanted pictures (drawn for a question labelled none) and the recall (drawn for those
labelled to draw), then the questions that missed. The targets: no unwanted picture, and at
least 90% recall (2026-11-15, four runs: maths 59/60, chemistry 44/44, no unwanted picture
of 108).

``--proxy-ca PATH``: where the app's pooled HTTP client cannot reach PubChem directly (a
sandbox behind an HTTPS proxy), PubChem is asked through one that honours the proxy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

CORPUS = Path(__file__).with_name("teaching_pictures_corpus.json")
MIN_RECALL = 0.9


def load(path: Path = CORPUS) -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {"maths": raw["maths"], "chemistry": raw["chemistry"]}


async def maths_drawn(settings: Any, prompt: str) -> bool:
    from app.modules.math.figure.build import build_figure_fence
    from app.modules.math.figure.read import read_figure

    reading = await read_figure(settings, prompt, [], asked=False)
    if reading is None or reading.kind == "none":
        return False
    return build_figure_fence(reading.model_dump_json(), [prompt]) is not None


async def chemistry_drawn(settings: Any, prompt: str) -> bool:
    from app.modules.chemistry import figure

    name = await figure.read_compound(settings, prompt, [])
    if name is None or not figure.written_by_user(name, [prompt]):
        return False
    smiles = await figure.pubchem_structure(name)
    return smiles is not None and figure.structure_fence(smiles, name) is not None


def _proxied_pubchem(ca_path: str) -> None:
    import httpx

    from app.gateways import pubchem_gateway

    client = httpx.AsyncClient(timeout=10, trust_env=True, verify=ca_path)
    setattr(pubchem_gateway, "get_pooled_client", lambda _timeout: client)  # noqa: B010


async def run(runs: int) -> int:
    from app.core.config import get_settings

    settings = get_settings()
    corpus = load()
    misses: dict[str, int] = {}
    failed = False
    for number in range(1, runs + 1):
        for subject, drawn_by in (("maths", maths_drawn), ("chemistry", chemistry_drawn)):
            entries = corpus[subject]
            drawn = await asyncio.gather(*(drawn_by(settings, e["prompt"]) for e in entries))
            wanted = [e for e, d in zip(entries, drawn, strict=True) if e["draw"] and d]
            unwanted = [e for e, d in zip(entries, drawn, strict=True) if not e["draw"] and d]
            labelled = sum(1 for e in entries if e["draw"])
            recall = len(wanted) / labelled if labelled else 1.0
            print(
                f"run {number} {subject}: unwanted {len(unwanted)}, "
                f"recall {len(wanted)}/{labelled} ({recall:.0%})"
            )
            failed = failed or bool(unwanted) or recall < MIN_RECALL
            for entry, was_drawn in zip(entries, drawn, strict=True):
                if was_drawn != entry["draw"]:
                    key = f"{subject}/{entry['id']}"
                    misses[key] = misses.get(key, 0) + 1
    for key, count in sorted(misses.items()):
        print(f"missed {count}/{runs}: {key}")
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--proxy-ca", default=None)
    args = parser.parse_args()
    if args.proxy_ca:
        _proxied_pubchem(args.proxy_ca)
    raise SystemExit(asyncio.run(run(args.runs)))


if __name__ == "__main__":
    main()
