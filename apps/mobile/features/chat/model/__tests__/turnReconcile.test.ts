import type { Message } from "@/lib/api";
import {
  DROPPED_TURN_POLLS,
  droppedTurnState,
  knownServerIds,
  mergeReconciledPage,
  pollDroppedTurn,
} from "@/features/chat/model/turnReconcile";

const id = (n: number) => `0190a000-0000-7000-8000-${String(n).padStart(12, "0")}`;
const msg = (messageId: string, role: Message["role"], content = messageId): Message => ({
  id: messageId,
  role,
  content,
  model: null,
  created_at: "t",
});

const before = [msg(id(1), "user"), msg(id(2), "assistant")];
const known = knownServerIds([...before, msg("local-9", "user"), msg("streaming", "assistant")]);

describe("knownServerIds", () => {
  it("keeps only server rows, never the turn's local bubbles", () => {
    expect([...known]).toEqual([id(1), id(2)]);
  });
});

describe("droppedTurnState", () => {
  it.each([
    ["missing", before],
    ["saved", [...before, msg(id(3), "user")]],
    ["answered", [...before, msg(id(3), "user"), msg(id(4), "assistant")]],
  ] as const)("%s", (state, page) => {
    expect(droppedTurnState([...page], known)).toBe(state);
  });

  it("an older reply is not this turn's answer", () => {
    expect(droppedTurnState([msg(id(3), "user"), ...before.slice(1)], known)).toBe("saved");
  });
});

describe("mergeReconciledPage", () => {
  it("swaps the local bubbles for the saved turn and keeps older loaded pages", () => {
    const older = msg(id(0), "assistant", "older page");
    const previous = [older, ...before, msg("local-9", "user", "q"), msg("streaming", "assistant", "")];
    const page = [...before, msg(id(3), "user", "q"), msg(id(4), "assistant", "a")];
    expect(mergeReconciledPage(previous, page).map((m) => m.id)).toEqual([
      id(0), id(1), id(2), id(3), id(4),
    ]);
  });

  it("a first turn has no older rows to keep", () => {
    const page = [msg(id(3), "user"), msg(id(4), "assistant")];
    expect(mergeReconciledPage([msg("local-1", "user"), msg("streaming", "assistant")], page)).toEqual(page);
  });
});

describe("pollDroppedTurn", () => {
  const wait = jest.fn(async () => {});
  beforeEach(() => wait.mockClear());

  it("stops at the first page that has the reply", async () => {
    const answered = [...before, msg(id(3), "user"), msg(id(4), "assistant")];
    const fetchPage = jest.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce([...before, msg(id(3), "user")])
      .mockResolvedValueOnce(answered);
    const result = await pollDroppedTurn({ fetchPage, known, stillWaiting: () => true, wait });
    expect(result).toEqual({ state: "answered", page: answered });
    expect(fetchPage).toHaveBeenCalledTimes(3);
  });

  it("reports the last state when the polls run out", async () => {
    const fetchPage = jest.fn().mockResolvedValue(before);
    const result = await pollDroppedTurn({ fetchPage, known, stillWaiting: () => true, wait });
    expect(result).toEqual({ state: "missing", page: before });
    expect(fetchPage).toHaveBeenCalledTimes(DROPPED_TURN_POLLS);
  });

  it("is unknown when no reload worked, and honours a shorter poll count", async () => {
    const fetchPage = jest.fn().mockRejectedValue(new Error("offline"));
    const result = await pollDroppedTurn({ fetchPage, known, stillWaiting: () => true, polls: 3, wait });
    expect(result).toEqual({ state: "unknown", page: null });
    expect(fetchPage).toHaveBeenCalledTimes(3);
  });

  it("returns null once the wait is abandoned", async () => {
    let waiting = true;
    const fetchPage = jest.fn(async () => {
      waiting = false; // Stop, a new send, or another chat while this reload ran
      return [...before, msg(id(3), "user"), msg(id(4), "assistant")];
    });
    expect(await pollDroppedTurn({ fetchPage, known, stillWaiting: () => waiting, wait })).toBeNull();
    expect(await pollDroppedTurn({ fetchPage, known, stillWaiting: () => false, wait })).toBeNull();
    expect(fetchPage).toHaveBeenCalledTimes(1);
  });
});
