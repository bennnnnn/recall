/**
 * The words of a live dictation, as OpenAI's transcription session sends them on the call's
 * data channel. Each stretch of speech is an item: its `delta` events add words as they are
 * spoken, and its `completed` event is the final text, which replaces them. Items are kept in
 * the order the server committed them (`input_audio_buffer.committed` names the item before),
 * since their completions may arrive out of order.
 */

type Segment = { id: string; partial: string; final: string | null };

export type DictationTranscript = { readonly segments: readonly Segment[] };

export const EMPTY_TRANSCRIPT: DictationTranscript = { segments: [] };

const DELTA = "conversation.item.input_audio_transcription.delta";
const COMPLETED = "conversation.item.input_audio_transcription.completed";
const FAILED = "conversation.item.input_audio_transcription.failed";
const COMMITTED = "input_audio_buffer.committed";

function text(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function withSegment(
  state: DictationTranscript,
  id: string,
  change: (segment: Segment) => Segment,
): DictationTranscript {
  const at = state.segments.findIndex((segment) => segment.id === id);
  if (at < 0) {
    return { segments: [...state.segments, change({ id, partial: "", final: null })] };
  }
  const segments = state.segments.slice();
  segments[at] = change(segments[at]);
  return { segments };
}

/** Put a committed item straight after the one the server says came before it. */
function placeCommitted(state: DictationTranscript, id: string, previous: string | null): DictationTranscript {
  const own = state.segments.find((segment) => segment.id === id) ?? { id, partial: "", final: null };
  const rest = state.segments.filter((segment) => segment.id !== id);
  const after = previous == null ? -1 : rest.findIndex((segment) => segment.id === previous);
  if (after < 0) {
    // No predecessor we know: an item already shown keeps its place, a new one goes last.
    return state.segments.some((segment) => segment.id === id) ? state : { segments: [...rest, own] };
  }
  return { segments: [...rest.slice(0, after + 1), own, ...rest.slice(after + 1)] };
}

/** The transcript after one data-channel event; any other event leaves it as it was. */
export function applyTranscriptEvent(
  state: DictationTranscript,
  event: Record<string, unknown>,
): DictationTranscript {
  const id = text(event.item_id);
  if (!id) return state;
  switch (event.type) {
    case DELTA: {
      const delta = text(event.delta);
      if (!delta) return state;
      return withSegment(state, id, (segment) =>
        segment.final == null ? { ...segment, partial: segment.partial + delta } : segment,
      );
    }
    case COMPLETED:
      return withSegment(state, id, (segment) => ({ ...segment, final: text(event.transcript) ?? segment.partial }));
    case FAILED:
      // The words already shown stay: they are what was heard.
      return withSegment(state, id, (segment) => ({ ...segment, final: segment.partial }));
    case COMMITTED:
      return placeCommitted(state, id, text(event.previous_item_id));
    default:
      return state;
  }
}

/** The text so far: each item's final text where it has one, else the words heard. */
export function transcriptText(state: DictationTranscript): string {
  return state.segments
    .map((segment) => (segment.final ?? segment.partial).trim())
    .filter(Boolean)
    .join(" ");
}

/** Every item the server opened has its final text. */
export function transcriptSettled(state: DictationTranscript): boolean {
  return state.segments.every((segment) => segment.final != null);
}

/** The server had nothing to commit when the take stopped (the user said nothing after the last item). */
export function isEmptyCommitError(event: Record<string, unknown>): boolean {
  if (event.type !== "error") return false;
  const error = event.error as { code?: unknown } | undefined;
  return error?.code === "input_audio_buffer_commit_empty";
}
