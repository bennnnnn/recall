/**
 * Render benchmarks for an assistant reply, drawn as the thread draws it (ReplyMarkdown:
 * the phone's own presentation, maths formatting and markdown). `pnpm perf` runs them under
 * Reassure; CI compares a pull request with main (`.github/workflows/mobile-ci.yml`, speed).
 *
 * The replies are frozen in support/perfReplies.json so main and a pull request time the
 * same text: a four-part worked calculus reply and one dense with inline maths (smart-chat,
 * November 2026), and the sweep corpus's revision-plan tables (s2-033) and Python reminder
 * app (cc-075). A benchmark's name is its key in the comparison: renaming one starts it over.
 */
import { useState } from "react";
import { Pressable } from "react-native";
import { fireEvent, screen } from "@testing-library/react-native";
import { measureRenders } from "reassure";

import { ReplyMarkdown } from "@/components/markdown/ReplyMarkdown";

import replies from "./support/perfReplies.json";

jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/components/LinkPreviewCard", () => ({ LinkPreviewCard: () => null }));

const NO_SOURCES: readonly { url: string }[] = [];
/** A reply's text arrives in about this many flushes (useStreamingDraft, ~30 a second). */
const FLUSHES = 24;

function Reply({ content, streaming = false }: { content: string; streaming?: boolean }) {
  return (
    <ReplyMarkdown
      content={content}
      streaming={streaming}
      presented={false}
      userText={null}
      sources={NO_SOURCES}
    />
  );
}

/** The reply as it streams: each press shows the next flush, the last one settles it. */
function StreamingReply({ text }: { text: string }) {
  const [flushes, setFlushes] = useState(1);
  const streaming = flushes < FLUSHES;
  const content = streaming ? text.slice(0, Math.ceil((text.length * flushes) / FLUSHES)) : text;
  return (
    <>
      <Pressable testID="next-flush" onPress={() => setFlushes((count) => count + 1)} />
      <Reply content={content} streaming={streaming} />
    </>
  );
}

test("worked maths reply", async () => {
  await measureRenders(<Reply content={replies.worked} />);
});

test("reply with many inline maths spans", async () => {
  await measureRenders(<Reply content={replies.inlineMaths} />);
});

test("worked maths reply while it streams", async () => {
  const scenario = async () => {
    for (let flush = 1; flush < FLUSHES; flush += 1) {
      await fireEvent.press(screen.getByTestId("next-flush"));
    }
  };
  await measureRenders(<StreamingReply text={replies.worked} />, { scenario });
});

test("reply with tables and code", async () => {
  await measureRenders(<Reply content={`${replies.tables}\n\n${replies.code}`} />);
});
