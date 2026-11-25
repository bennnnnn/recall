import {
  applyTranscriptEvent,
  EMPTY_TRANSCRIPT,
  isEmptyCommitError,
  transcriptSettled,
  transcriptText,
  type DictationTranscript,
} from "@/features/speech/model/dictationTranscript";

const delta = (item: string, text: string) => ({
  type: "conversation.item.input_audio_transcription.delta",
  item_id: item,
  delta: text,
});
const completed = (item: string, transcript: string) => ({
  type: "conversation.item.input_audio_transcription.completed",
  item_id: item,
  transcript,
});
const committed = (item: string, previous: string | null) => ({
  type: "input_audio_buffer.committed",
  item_id: item,
  previous_item_id: previous,
});

function play(events: Record<string, unknown>[]): DictationTranscript {
  return events.reduce(applyTranscriptEvent, EMPTY_TRANSCRIPT);
}

describe("a live dictation's transcript", () => {
  it("grows word by word as the deltas arrive (OpenAI's own spacing, trimmed)", () => {
    let state = EMPTY_TRANSCRIPT;
    const seen: string[] = [];
    for (const word of [" Rem", "ind", " me", " to", " buy", " milk"]) {
      state = applyTranscriptEvent(state, delta("a", word));
      seen.push(transcriptText(state));
    }
    expect(seen).toEqual(["Rem", "Remind", "Remind me", "Remind me to", "Remind me to buy", "Remind me to buy milk"]);
    expect(transcriptSettled(state)).toBe(false);
  });

  it("replaces a stretch's words with its final text", () => {
    const state = play([delta("a", " remind me"), delta("a", " to by"), completed("a", "Remind me to buy")]);
    expect(transcriptText(state)).toBe("Remind me to buy");
    expect(transcriptSettled(state)).toBe(true);
    // A late delta for a finished stretch changes nothing.
    expect(transcriptText(applyTranscriptEvent(state, delta("a", " milk")))).toBe("Remind me to buy");
  });

  it("keeps the server's commit order when completions arrive out of order", () => {
    const state = play([
      committed("a", null),
      delta("a", " first"),
      committed("b", "a"),
      completed("b", "second."),
      completed("a", "First,"),
    ]);
    expect(transcriptText(state)).toBe("First, second.");
  });

  it("puts a stretch whose words came before its commit after the one the server names", () => {
    const state = play([delta("b", " later"), delta("a", " earlier"), committed("b", "a")]);
    expect(transcriptText(state)).toBe("earlier later");
  });

  it("keeps the words heard when a stretch fails to transcribe", () => {
    const state = play([
      delta("a", " half a sentence"),
      { type: "conversation.item.input_audio_transcription.failed", item_id: "a", error: {} },
    ]);
    expect(transcriptText(state)).toBe("half a sentence");
    expect(transcriptSettled(state)).toBe(true);
  });

  it("ignores events that carry no words", () => {
    const state = play([{ type: "session.created" }, { type: "input_audio_buffer.speech_started", item_id: "a" }]);
    expect(state).toBe(EMPTY_TRANSCRIPT);
  });

  it("knows the error for a stop with nothing left to commit", () => {
    expect(isEmptyCommitError({ type: "error", error: { code: "input_audio_buffer_commit_empty" } })).toBe(true);
    expect(isEmptyCommitError({ type: "error", error: { code: "other" } })).toBe(false);
  });
});
