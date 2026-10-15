#!/usr/bin/env -S uv run python
"""Send the behavior battery to a running API and write what Recall answered.

The prompts and what a good reply looks like come from
apps/api/app/tests/behavior/cases.py, the same list CI routes offline. This run
goes through the real HTTP stream, so with a provider key in apps/api/.env the
replies come from the real model; without one they are the stand-in model's, and
only routing (search, photos, solvers, instant replies) is worth reading.

Each prompt gets a fresh chat on dedicated battery accounts (one free, one Pro),
whose old chats are deleted first. The report lands in tmp/battery/.

Usage (the API must be running: ./scripts/dev.sh up, or ./scripts/dev.sh api):
    ./scripts/dev.sh battery                       # every prompt
    ./scripts/dev.sh battery --category teaching   # one category
    ./scripts/dev.sh battery --only map-where-is,photo-new-product
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.modules.chat.prompt_constants import lesson_step  # noqa: E402
from app.tests.behavior.cases import CASES, CATEGORIES, Case  # noqa: E402

TIMEZONE = "Africa/Nairobi"
# The API allows 30 chat messages a minute per user; stay under it.
PACE_SECONDS = 2.2
TURN_TIMEOUT = 180.0
MOCK_REPLY_START = "I'm Recall (mock mode)"
MOCK_SEARCH_URL = "https://example.com/mock-search"
LOCATION_OFF_START = "I don't have your location yet"
IMAGE_RE = re.compile(r"\[Image: (/attachments/[^\]]+)\]")


@dataclass
class Turn:
    """One prompt as the app saw it."""

    reply: str = ""
    phases: list[str] = field(default_factory=list)
    model: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    error: str | None = None
    first_token_s: float | None = None
    total_s: float = 0.0

    @property
    def photo(self) -> bool:
        return self.model == "image-search-model"

    @property
    def generated(self) -> bool:
        return self.model == "image-gen-model"

    def route(self) -> str:
        parts: list[str] = []
        if self.reply.startswith("```clock"):
            parts.append("clock card")
        elif self.reply.startswith(LOCATION_OFF_START):
            parts.append("asked to turn on location")
        if self.sources:
            parts.append(f"searched ({len(self.sources)} sources)")
        if self.photo:
            parts.append("photo")
        elif self.generated:
            parts.append("generated image")
        phases = [p for p in dict.fromkeys(self.phases) if p not in {"thinking", "writing"}]
        if phases:
            parts.append("status: " + ", ".join(phases))
        if self.model and self.model not in {"image-search-model", "image-gen-model"}:
            parts.append(f"model {self.model}")
        return "; ".join(parts) or "plain reply"


class Battery:
    def __init__(self, api: str) -> None:
        self.api = api.rstrip("/")
        self.client = httpx.Client(base_url=self.api, timeout=30.0)
        self.tokens: dict[bool, str] = {}
        self.location: dict[bool, str | None] = {}
        self.last_send = 0.0

    def _headers(self, pro: bool) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[pro]}"}

    def check_api(self) -> None:
        try:
            self.client.get("/health").raise_for_status()
        except httpx.HTTPError:
            sys.exit(
                f"The API is not answering on {self.api}. Start it with "
                "./scripts/dev.sh up (or ./scripts/dev.sh api), then run this again."
            )

    def login(self, pro: bool) -> None:
        email = "battery-pro@recall.local" if pro else "battery@recall.local"
        response = self.client.post("/auth/dev", json={"email": email, "name": "Bini"})
        if response.status_code in {403, 404}:
            sys.exit("Dev login is off. Set DEV_AUTH_ENABLED=true in apps/api/.env.")
        response.raise_for_status()
        self.tokens[pro] = response.json()["access_token"]
        headers = self._headers(pro)
        if pro:
            self.client.post("/auth/me/pro-dev", headers=headers).raise_for_status()
        self.client.patch(
            "/auth/me",
            headers=headers,
            json={"timezone": TIMEZONE, "location_enabled": False, "location": None},
        ).raise_for_status()
        self.location[pro] = None
        # A fresh start: last run's chats go.
        self.client.delete("/chats", headers=headers).raise_for_status()

    def _reset_quota(self, pro: bool) -> None:
        """A battery spends a day's free tokens; the dev reset keeps every prompt answerable."""
        response = self.client.post("/chats/usage/today/reset", headers=self._headers(pro))
        if response.status_code >= 400:
            sys.exit(
                f"Could not reset the test account's daily quota (HTTP {response.status_code}). "
                "Run the battery against a local development API."
            )

    def _set_location(self, pro: bool, location: str | None) -> None:
        if self.location[pro] == location:
            return
        self.client.patch(
            "/auth/me",
            headers=self._headers(pro),
            json={"location": location, "location_enabled": location is not None},
        ).raise_for_status()
        self.location[pro] = location

    def _send(self, pro: bool, chat_id: str, content: str, location: str | None) -> Turn:
        wait = PACE_SECONDS - (time.monotonic() - self.last_send)
        if wait > 0:
            time.sleep(wait)
        self.last_send = time.monotonic()
        turn = Turn()
        body = {"content": content, "client_timezone": TIMEZONE, "client_location": location}
        started = time.monotonic()
        tokens: list[str] = []
        try:
            with self.client.stream(
                "POST",
                f"/chats/{chat_id}/messages/stream",
                headers=self._headers(pro),
                json=body,
                timeout=TURN_TIMEOUT,
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    turn.error = f"HTTP {response.status_code}: {response.text[:300]}"
                    return turn
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    kind = event.get("type")
                    if kind == "token":
                        if turn.first_token_s is None:
                            turn.first_token_s = time.monotonic() - started
                        tokens.append(str(event.get("content") or ""))
                    elif kind == "status" and event.get("phase"):
                        turn.phases.append(str(event["phase"]))
                    elif kind == "stream_end":
                        turn.model = event.get("resolved_model") or turn.model
                    elif kind == "done":
                        turn.model = event.get("resolved_model") or turn.model
                        if event.get("final_content"):
                            tokens = [str(event["final_content"])]
                        sources = event.get("search_sources")
                        if isinstance(sources, str) and sources:
                            try:
                                sources = json.loads(sources)
                            except json.JSONDecodeError:
                                sources = []
                        turn.sources = sources if isinstance(sources, list) else []
                    elif kind == "error":
                        turn.error = str(event.get("message") or event)
        except httpx.HTTPError as exc:
            turn.error = f"{type(exc).__name__}: {exc}"
        turn.total_s = time.monotonic() - started
        turn.reply = "".join(tokens).strip()
        turn.images = IMAGE_RE.findall(turn.reply)
        return turn

    def run(self, case: Case) -> Turn:
        self._reset_quota(case.pro)
        self._set_location(case.pro, case.location)
        created = self.client.post(
            "/chats", headers=self._headers(case.pro), json={"model": "auto"}
        )
        created.raise_for_status()
        chat_id = created.json()["id"]
        # Earlier turns are asked for real, so the chat has the history the case needs.
        for role, text in case.history:
            if role == "user":
                self._send(case.pro, chat_id, text, case.location)
        return self._send(case.pro, chat_id, case.prompt, case.location)


def check(case: Case, turn: Turn) -> list[str]:
    """Where the live turn did not do what the case expects, for what HTTP can see."""
    expect = case.expect
    misses: list[str] = []
    if turn.error:
        return ["error"]
    wants_photo = bool(expect.photo) or bool(expect.photo_not)
    if wants_photo and not turn.photo:
        misses.append("no photo")
    if expect.photo == "" and turn.photo and not expect.answer_photo:
        misses.append("photo shown")
    if expect.answer_photo and not turn.photo:
        misses.append("no photo above the answer")
    if expect.image_gen is True and not turn.generated:
        misses.append("no generated image")
    if expect.image_gen is False and turn.generated:
        misses.append("generated an image")
    # A lookup or generated image is the whole reply; an answer photo sits above text.
    if (turn.photo and not expect.answer_photo) or turn.generated:
        return misses
    if expect.search == "yes" and not turn.sources:
        misses.append("did not search")
    if expect.search == "no" and turn.sources:
        misses.append("searched")
    if expect.instant == "clock" and not turn.reply.startswith("```clock"):
        misses.append("no clock card")
    if expect.instant == "location" and not turn.reply.startswith(LOCATION_OFF_START):
        misses.append("did not ask for location")
    lesson = {"teaching", "walkthrough"} & set(expect.hints)
    if lesson and lesson_step(turn.reply) is None:
        misses.append("no lesson title")
    if lesson and "```quiz" not in turn.reply:
        misses.append("no quiz card")
    if "map" in expect.hints and "```map" not in turn.reply:
        misses.append("no map card")
    if "map" in expect.no_hints and "```map" in turn.reply:
        misses.append("map card shown")
    return misses


def _select(args: argparse.Namespace) -> list[Case]:
    cases = list(CASES)
    if args.category:
        if args.category not in CATEGORIES:
            sys.exit(f"Unknown category {args.category!r}. One of: {', '.join(CATEGORIES)}")
        cases = [case for case in cases if case.category == args.category]
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        unknown = wanted - {case.id for case in CASES}
        if unknown:
            sys.exit(f"Unknown case ids: {', '.join(sorted(unknown))}")
        cases = [case for case in cases if case.id in wanted]
    return cases


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def write_report(results: list[tuple[Case, Turn]], out_dir: Path, api: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    mock = any(turn.reply.startswith(MOCK_REPLY_START) for _, turn in results)
    mock_search = any(
        source.get("url") == MOCK_SEARCH_URL for _, turn in results for source in turn.sources
    )
    misses = {case.id: check(case, turn) for case, turn in results}
    lines = [
        f"# Behavior battery — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"API: {api}. {len(results)} prompts, "
        f"{sum(1 for found in misses.values() if not found)} as expected.",
        "",
        "- Replies: "
        + (
            "**stand-in model** (no OPENROUTER_API_KEY), so read the routing, not the wording."
            if mock
            else "real model."
        ),
    ]
    if mock_search:
        lines.append(
            "- Web search returned **stand-in results** (no TAVILY_API_KEY). Photo lookups "
            "need that key too, so without it they come back as text."
        )
    lines += [
        "",
        "| Case | Prompt | What happened | Check | First token | Known gap |",
        "|---|---|---|---|---|---|",
    ]
    for case, turn in results:
        first = f"{turn.first_token_s:.1f}s" if turn.first_token_s is not None else "—"
        happened = f"error: {turn.error}" if turn.error else turn.route()
        verdict = "✓" if not misses[case.id] else "✗ " + ", ".join(misses[case.id])
        lines.append(
            f"| `{case.id}` | {_cell(case.prompt)} | {_cell(happened)} | {_cell(verdict)} "
            f"| {first} | {_cell(case.gap or '')} |"
        )
    current = ""
    for case, turn in results:
        if case.category != current:
            current = case.category
            lines += ["", f"## {current.capitalize()}"]
        lines += [
            "",
            f"### `{case.id}` — {case.prompt}",
            "",
            f"- **Good reply:** {case.good}",
        ]
        if case.gap:
            lines.append(f"- **Known gap:** {case.gap}")
        if case.history:
            lines.append(
                "- **Asked first:** " + " / ".join(t for r, t in case.history if r == "user")
            )
        if case.location:
            lines.append(f"- **Location:** {case.location}")
        if case.pro:
            lines.append("- **Plan:** Pro")
        lines.append(f"- **What happened:** {turn.route()} ({turn.total_s:.1f}s)")
        if misses[case.id]:
            lines.append(f"- **Not as expected:** {', '.join(misses[case.id])}")
        for source in turn.sources[:5]:
            title = source.get("title") or source.get("url") or ""
            lines.append(f"  - source: {_cell(str(title))} {source.get('url', '')}")
        for image in turn.images:
            lines.append(f"  - image: {api}{image}")
        if turn.error:
            lines += ["", f"> **Error:** {turn.error}"]
        lines += [
            "",
            "<details open><summary>Reply</summary>",
            "",
            turn.reply or "_(empty)_",
            "",
            "</details>",
        ]
    report = out_dir / f"{stamp}.md"
    report.write_text("\n".join(lines) + "\n")
    (out_dir / f"{stamp}.json").write_text(
        json.dumps(
            [{"case": case.id, "prompt": case.prompt, **asdict(turn)} for case, turn in results],
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    _prune_old_reports(out_dir)
    return report


# Each run adds about 80 KB, and nothing removed old runs.
_KEEP_REPORTS = 20


def _prune_old_reports(out_dir: Path) -> None:
    """Keep the newest reports; only names this script writes are touched."""
    stamps = sorted(
        (path.stem for path in out_dir.glob("*.md") if re.fullmatch(r"\d{8}-\d{6}", path.stem)),
        reverse=True,
    )
    for stamp in stamps[_KEEP_REPORTS:]:
        for suffix in (".md", ".json"):
            (out_dir / f"{stamp}{suffix}").unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send the behavior battery to a running API.")
    parser.add_argument("--api", default=os.environ.get("BATTERY_API", "http://127.0.0.1:8000"))
    parser.add_argument("--category", help=f"one of: {', '.join(CATEGORIES)}")
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--out", default=str(ROOT / "tmp" / "battery"))
    args = parser.parse_args()

    cases = _select(args)
    battery = Battery(args.api)
    battery.check_api()
    for pro in sorted({case.pro for case in cases}):
        battery.login(pro)

    results: list[tuple[Case, Turn]] = []
    for index, case in enumerate(cases, 1):
        turn = battery.run(case)
        results.append((case, turn))
        found = check(case, turn)
        mark = "✗" if found else "✓"
        note = f"  ← {', '.join(found)}" if found else ""
        print(f"[{index:>2}/{len(cases)}] {mark} {case.id:<28} {turn.route()}{note}", flush=True)

    report = write_report(results, Path(args.out), battery.api)
    failed = sum(1 for _, turn in results if turn.error)
    print(f"\nReport: {report}")
    if failed:
        print(f"{failed} prompt(s) failed; see the report.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
