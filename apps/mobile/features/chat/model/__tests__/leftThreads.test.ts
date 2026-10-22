import { keepLeftThread, takeRecentLeftThread, type LeftThread } from "@/features/chat/model/leftThreads";
import { FOREGROUND_STALE_MS } from "@/lib/foregroundRefresh";

jest.mock("react-native", () => ({ AppState: { addEventListener: jest.fn() } }));

const thread = (at: number): LeftThread => ({ messages: [], hasMore: false, at });

it("gives a thread left moments ago back once", () => {
  const threads = new Map<string, LeftThread>();
  keepLeftThread(threads, "a", thread(1_000));
  expect(takeRecentLeftThread(threads, "a", 1_000 + FOREGROUND_STALE_MS.chatMessages - 1)).not.toBeNull();
  expect(takeRecentLeftThread(threads, "a", 1_001)).toBeNull();
});

it("does not give back a thread left too long ago", () => {
  const threads = new Map<string, LeftThread>();
  keepLeftThread(threads, "a", thread(0));
  expect(takeRecentLeftThread(threads, "a", FOREGROUND_STALE_MS.chatMessages)).toBeNull();
});

it("keeps only the last few threads", () => {
  const threads = new Map<string, LeftThread>();
  for (const id of ["a", "b", "c", "d", "e", "f"]) keepLeftThread(threads, id, thread(0));
  expect([...threads.keys()]).toEqual(["b", "c", "d", "e", "f"]);
});
