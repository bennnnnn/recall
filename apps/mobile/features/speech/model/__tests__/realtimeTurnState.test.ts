import {
  initialRealtimeTurnState,
  reduceRealtimeTurn,
  type RealtimeTurnCommand,
  type RealtimeTurnEvent,
  type RealtimeTurnState,
} from "@/features/speech/model/realtimeTurnState";

// realtimeTools (the function-call parser) sits beside the lookup client.
jest.mock("@/features/speech/api", () => ({ speechApi: {} }));

const server = (event: Record<string, unknown>): RealtimeTurnEvent => ({ type: "server_event", event, receivedAt: 7 });

/** Applies events in order; returns the last state and every command except logs. */
function run(state: RealtimeTurnState, ...events: RealtimeTurnEvent[]) {
  const commands: RealtimeTurnCommand[] = [];
  for (const event of events) {
    const step = reduceRealtimeTurn(state, event);
    state = step.state;
    commands.push(...step.commands.filter((command) => command.type !== "log"));
  }
  return { state, commands };
}

/** Ready for turns, the user said u1 and the assistant is answering it as a1. */
function replying(bargeIn: boolean): RealtimeTurnState {
  return run(
    initialRealtimeTurnState(bargeIn),
    { type: "session_ready", reason: "test" },
    server({ type: "input_audio_buffer.speech_started", item_id: "u1" }),
    server({ type: "input_audio_buffer.speech_stopped" }),
    server({ type: "response.created", response: { id: "a1" } }),
    server({ type: "response.output_audio_transcript.delta", response_id: "a1", delta: "The capital" }),
  ).state;
}

describe("reduceRealtimeTurn: barge-in", () => {
  it("interrupts the reply when the user talks over it and starts a new turn", () => {
    const before = replying(true);
    const { state, commands } = run(before, server({ type: "input_audio_buffer.speech_started", item_id: "u2" }));
    expect(commands).toEqual([
      { type: "emit", event: { type: "response_interrupted" } },
      { type: "clear_timer", timer: "mic_resume" },
      { type: "emit", event: { type: "speech_started", turnId: "u2" } },
    ]);
    expect(state).toMatchObject({ assistantSpeaking: false, activeResponseId: null, assistantTranscript: "" });
    expect(state.turnEpoch).toBe(before.turnEpoch + 1);
  });

  it("keeps the mic open for the reply and drops the interrupted reply's late events", () => {
    const opened = run(replying(true), server({ type: "response.created", response: { id: "a2" } }));
    expect(opened.commands).toContainEqual({ type: "set_mic", enabled: true });
    const late = run(
      replying(true),
      server({ type: "input_audio_buffer.speech_started", item_id: "u2" }),
      server({ type: "response.output_audio_transcript.delta", response_id: "a1", delta: "stale" }),
      server({ type: "response.done", response: { id: "a1", output: [] } }),
    );
    expect(late.commands.filter((command) => command.type === "emit")).toHaveLength(2);
  });

  it("cancels a reply created while the user is still speaking", () => {
    const speaking = run(replying(true), server({ type: "input_audio_buffer.speech_started", item_id: "u2" })).state;
    const { state, commands } = run(speaking, server({ type: "response.created", response: { id: "a2" } }));
    expect(commands).toEqual([{ type: "send", payload: { type: "response.cancel", response_id: "a2" } }]);
    expect(state.activeResponseId).toBeNull();
  });

  it("finishes the reply when playback stops, or 12 s after response.done without a stop", () => {
    const done = run(replying(true), server({ type: "response.done", response: { id: "a1", output: [] } }));
    expect(done.commands).toEqual([
      { type: "start_timer", timer: "mic_resume", ms: 12_000, then: { type: "playback_fallback" } },
    ]);
    expect(run(done.state, { type: "playback_fallback" }).commands).toEqual([
      { type: "emit", event: { type: "response_done" } },
    ]);
    expect(run(done.state, server({ type: "output_audio_buffer.stopped", response_id: "a1" })).commands).toEqual([
      { type: "clear_timer", timer: "mic_resume" },
      { type: "emit", event: { type: "response_done" } },
    ]);
  });
});

describe("reduceRealtimeTurn: echo drop (half duplex)", () => {
  it("closes the mic for the reply and reopens it 500 ms after playback", () => {
    const created = run(
      run(initialRealtimeTurnState(false), { type: "session_ready", reason: "test" }).state,
      server({ type: "input_audio_buffer.speech_started", item_id: "u1" }),
      server({ type: "input_audio_buffer.speech_stopped" }),
    );
    expect(created.commands).toContainEqual({ type: "set_mic", enabled: false });
    const stopped = run(replying(false), server({ type: "output_audio_buffer.stopped", response_id: "a1" }));
    expect(stopped.commands).toEqual([
      { type: "start_timer", timer: "mic_resume", ms: 500, then: { type: "resume_mic" } },
    ]);
    expect(run(stopped.state, { type: "resume_mic" }).commands).toEqual([{ type: "set_mic", enabled: true }]);
  });

  it("clears speech heard during the reply and cancels a reply the server starts for it", () => {
    const { state, commands } = run(
      replying(false),
      server({ type: "input_audio_buffer.speech_started", item_id: "echo" }),
      server({ type: "response.created", response: { id: "a2" } }),
    );
    expect(commands).toEqual([
      { type: "send", payload: { type: "input_audio_buffer.clear" } },
      { type: "send", payload: { type: "input_audio_buffer.clear" } },
      { type: "send", payload: { type: "response.cancel" } },
    ]);
    expect(state).toMatchObject({ suppressCurrentInputTurn: true, acceptedUserUtterance: false, activeInputId: "u1" });
  });

  // An echo heard during the reply kept the user's own turn active; the echo's drop flag was
  // then applied to that turn's late line, which was saved with no line (and the server keeps
  // no reply without one).
  it("keeps the user's late line while an echo of the reply is being dropped", () => {
    const { commands } = run(
      replying(false),
      server({ type: "input_audio_buffer.speech_started", item_id: "echo" }),
      server({ type: "conversation.item.input_audio_transcription.completed", item_id: "u1", transcript: "What is the capital of France?" }),
      server({ type: "conversation.item.input_audio_transcription.completed", item_id: "echo", transcript: "The capital" }),
      server({ type: "conversation.item.input_audio_transcription.completed", transcript: "the capital" }),
    );
    const lines = commands.flatMap((command) =>
      command.type === "emit" && command.event.type === "user_transcript" ? [command.event] : []);
    expect(lines).toEqual([{ type: "user_transcript", text: "What is the capital of France?", turnId: "u1" }]);
  });

  it("drops a transcript that repeats the assistant's last line", () => {
    const { commands } = run(
      replying(false),
      server({ type: "response.output_audio_transcript.done", response_id: "a1", transcript: "The capital is Paris." }),
      server({ type: "conversation.item.input_audio_transcription.completed", item_id: "u1", transcript: "is Paris" }),
    );
    expect(commands.at(-1)).toEqual({ type: "send", payload: { type: "input_audio_buffer.clear" } });
    expect(commands).not.toContainEqual(expect.objectContaining({ event: expect.objectContaining({ type: "user_transcript" }) }));
  });
});

describe("reduceRealtimeTurn: the user's line and the reply it asks for", () => {
  const ready = () => run(initialRealtimeTurnState(true), { type: "session_ready", reason: "test" }).state;
  const emitted = (commands: RealtimeTurnCommand[]) =>
    commands.flatMap((command) => (command.type === "emit" ? [command.event] : []));

  it.each<[string, RealtimeTurnEvent[], boolean]>([
    ["asks for a reply when the user stops talking", [], true],
    ["asks for none when the user muted mid-sentence", [{ type: "set_muted", muted: true }], false],
  ])("%s", (_label, between, replying) => {
    const { commands } = run(
      ready(),
      server({ type: "input_audio_buffer.speech_started", item_id: "u1" }),
      ...between,
      server({ type: "input_audio_buffer.speech_stopped", item_id: "u1" }),
    );
    expect(emitted(commands)).toContainEqual({ type: "speech_stopped", replying });
    expect(commands.some((command) => command.type === "send" && command.payload.type === "response.create")).toBe(replying);
  });

  it("names the utterance a late line transcribes, and drops one never accepted", () => {
    const { commands } = run(
      ready(),
      server({ type: "input_audio_buffer.speech_started", item_id: "u1" }),
      server({ type: "input_audio_buffer.speech_stopped", item_id: "u1" }),
      server({ type: "input_audio_buffer.speech_started", item_id: "u2" }),
      server({ type: "conversation.item.input_audio_transcription.completed", item_id: "u1", transcript: "First" }),
      server({ type: "conversation.item.input_audio_transcription.completed", item_id: "u0", transcript: "Never heard" }),
      server({ type: "conversation.item.input_audio_transcription.completed", item_id: "u2", transcript: "Second" }),
    );
    expect(emitted(commands).filter((event) => event.type === "user_transcript")).toEqual([
      { type: "user_transcript", text: "First", turnId: "u1" },
      { type: "user_transcript", text: "Second", turnId: "u2" },
    ]);
  });
});

describe("reduceRealtimeTurn: turn rules", () => {
  it("answers a lookup from an older turn as cancelled and asks for no reply", () => {
    const call = { type: "function_call", name: "web_search", call_id: "t1", arguments: '{"query":"q"}' };
    const asked = run(replying(true), server({ type: "response.done", response: { id: "a1", output: [call] } }));
    expect(asked.commands).toEqual([
      { type: "run_tools", epoch: 1, turnId: "u1", calls: [{ call, withinLimit: true }] },
    ]);
    const { commands } = run(
      asked.state,
      { type: "cancel_response" },
      { type: "tool_output", epoch: 1, callId: "t1", result: { content: "Old", sources: [{ title: "S", url: "https://s" }] } },
      { type: "tools_settled", epoch: 1 },
    );
    expect(commands.filter((command) => command.type === "send").map((command) => command.payload)).toEqual([
      { type: "response.cancel" },
      { type: "output_audio_buffer.clear" },
      {
        type: "conversation.item.create",
        item: { type: "function_call_output", call_id: "t1", output: '{"content":"Lookup cancelled by a new user turn."}' },
      },
    ]);
  });

  it("does nothing with messages once closed", () => {
    const closed = run(replying(true), { type: "close" }).state;
    expect(reduceRealtimeTurn(closed, server({ type: "error", error: { message: "x" } })).commands).toEqual([]);
  });

  it("never changes the state it is given", () => {
    const state = Object.freeze(replying(false));
    expect(() => run(state, server({ type: "input_audio_buffer.speech_started", item_id: "u2" }), { type: "set_muted", muted: true })).not.toThrow();
    expect(state.userMuted).toBe(false);
  });
});

describe("reduceRealtimeTurn: a failed connection", () => {
  it.each(["peer_failed", "channel_failed"] as const)("%s is a fatal error, so the session closes", (type) => {
    const { commands } = run(replying(true), { type, message: "network lost" });
    expect(commands).toContainEqual({ type: "emit", event: { type: "error", message: "network lost", fatal: true } });
  });

  it("a server error event is not fatal: the session goes on", () => {
    const { commands } = run(replying(true), server({ type: "error", error: { message: "rate limited" } }));
    expect(commands).toContainEqual({ type: "emit", event: { type: "error", message: "rate limited" } });
  });
});

describe("reduceRealtimeTurn: the reply's audio playing", () => {
  const playing = { type: "emit", event: { type: "output_audio", playing: true } };
  const stopped = { type: "emit", event: { type: "output_audio", playing: false } };
  const started = server({ type: "output_audio_buffer.started", response_id: "a1" });

  it.each([true, false])("reports playback start and stop once each (barge-in: %s)", (bargeIn) => {
    const { commands } = run(
      replying(bargeIn),
      started,
      started,
      server({ type: "output_audio_buffer.stopped", response_id: "a1" }),
      server({ type: "output_audio_buffer.stopped", response_id: "a1" }),
    );
    const audio = commands.filter((c) => c.type === "emit" && c.event.type === "output_audio");
    expect(audio).toEqual([playing, stopped]);
  });

  it.each<[string, RealtimeTurnEvent]>([
    ["the user talks over it", server({ type: "input_audio_buffer.speech_started", item_id: "u2" })],
    ["the reply is cancelled", { type: "cancel_response" }],
    ["the buffer is cleared", server({ type: "output_audio_buffer.cleared", response_id: "a1" })],
    ["the server errors", server({ type: "error", error: { message: "boom" } })],
  ])("stops when %s", (_label, event) => {
    const { state, commands } = run(run(replying(true), started).state, event);
    expect(commands).toContainEqual(stopped);
    expect(state.audioPlaying).toBe(false);
  });

  // The mic fallback runs 12 s from response.done; a long reply still plays after it.
  it.each<RealtimeTurnEvent>([{ type: "playback_fallback" }, { type: "resume_mic" }])(
    "keeps playing through the mic fallback until the stop event: %j",
    (fallback) => {
      const { state, commands } = run(
        replying(true),
        started,
        server({ type: "response.done", response: { id: "a1", output: [] } }),
        fallback,
      );
      expect(commands).not.toContainEqual(stopped);
      expect(state.audioPlaying).toBe(true);
      const after = run(state, server({ type: "output_audio_buffer.stopped", response_id: "a1" }));
      expect(after.commands).toContainEqual(stopped);
    },
  );

  // A lookup's spoken preamble can still be playing when the follow-up response begins.
  it("ends playback on the playing response's stop, even after a newer response began", () => {
    const { state, commands } = run(
      run(replying(true), started).state,
      server({ type: "response.created", response: { id: "a2" } }),
      server({ type: "output_audio_buffer.stopped", response_id: "a1" }),
    );
    expect(commands).toContainEqual(stopped);
    expect(state.audioPlaying).toBe(false);
  });
});
