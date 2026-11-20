"""Replay the 80-message "Friend getting married" chat through a running API's live SSE path.

From apps/api, with the API running (its provider key in that one command's environment):
    uv run python ../../docs/qa/natural-chat/replay.py <api_url> <email> <out.json>
    uv run python ../../docs/qa/natural-chat/replay.py <api_url> <email> <out.json> \
        --extra lines.json

One fresh chat, the owner's settings for this chat (Pro, tone casual, Emoji "Lots", first name
Bini, English, America/Los_Angeles). After each turn it waits for the job queue to drain, so
the summary fold and memory run between messages as they would for a person typing. Point
REDIS_URL at the API's own Redis database: a queue shared with another API lets that API's
worker run this chat's jobs with its own code. Stops on an out-of-credit (402) error rather
than send the rest to nothing. ``--extra`` takes a JSON list of lines, each its own fresh chat
(a list inside it is one chat of several lines).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api"))
import battery  # noqa: E402

TURNS = ROOT / "apps/api/app/tests/behavior/replays/friend_getting_married.json"
TIMEZONE = "America/Los_Angeles"
SETTINGS = {
    "name": "Bini",
    "response_tone": "casual",
    "emoji_use": "more",
    "locale": "en",
    "timezone": TIMEZONE,
    "location_enabled": False,
    "location": None,
    "ai_data_consent": True,
    "memory_enabled": True,
    "memory_include_sensitive": True,
    "web_search_enabled": True,
    "follow_up_suggestions_enabled": True,
    "default_model": "auto",
}


def _fresh_account(run: battery.Battery, email: str) -> dict[str, str]:
    response = run.client.post("/auth/dev", json={"email": email, "name": "Bini"})
    response.raise_for_status()
    run.tokens[True] = response.json()["access_token"]
    headers = run._headers(True)
    run.client.post("/auth/me/pro-dev", headers=headers).raise_for_status()
    run.client.patch("/auth/me", headers=headers, json=SETTINGS).raise_for_status()
    run.client.delete("/chats", headers=headers).raise_for_status()
    battery._jobs_settled(60)
    for _ in range(30):
        cleared = run.client.delete("/memories", headers=headers)
        if cleared.status_code != 409:
            cleared.raise_for_status()
            break
        time.sleep(1)
    return headers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("api")
    parser.add_argument("email")
    parser.add_argument("out")
    parser.add_argument("--extra")
    args = parser.parse_args()
    battery.TIMEZONE = TIMEZONE
    run = battery.Battery(args.api)
    run.check_api()
    headers = _fresh_account(run, args.email)
    if args.extra:
        chats = [[x] if isinstance(x, str) else x for x in json.loads(Path(args.extra).read_text())]
    else:
        chats = [[t["user"] for t in json.loads(TURNS.read_text())["turns"]]]
    out, results = Path(args.out), []
    for group, lines in enumerate(chats):
        created = run.client.post("/chats", headers=headers, json={})
        created.raise_for_status()
        chat_id = created.json()["id"]
        for index, text in enumerate(lines):
            run.client.post("/chats/usage/today/reset", headers=headers)
            turn = run._send(True, chat_id, text, None)
            settled = battery._jobs_settled(120)
            results.append(
                {"group": group, "turn": index, "user": text, "settled": settled, **asdict(turn)}
            )
            out.write_text(json.dumps(results, ensure_ascii=False, indent=1))
            print(
                f"[{group}:{index}] {turn.model} {turn.total_s:.0f}s err={turn.error}", flush=True
            )
            if turn.error and ("402" in turn.error or "credit" in turn.error.lower()):
                sys.exit("Stopped: the provider is out of credits (402).")


if __name__ == "__main__":
    main()
