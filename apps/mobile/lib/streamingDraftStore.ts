import type { SearchSource } from "@/lib/api";

export type StreamingDraft = {
  content: string;
  search_sources?: SearchSource[];
  status?: string;
  reasoning?: string;
};

type Listener = () => void;

let draft: StreamingDraft | null = null;
const listeners = new Set<Listener>();

export function getStreamingDraft(): StreamingDraft | null {
  return draft;
}

export function getStreamingDraftContentLength(): number {
  return draft?.content.length ?? 0;
}

export function publishStreamingDraft(next: StreamingDraft | null): void {
  draft = next;
  listeners.forEach((listener) => listener());
}

export function subscribeStreamingDraft(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function resetStreamingDraftStore(): void {
  draft = null;
  listeners.clear();
}
