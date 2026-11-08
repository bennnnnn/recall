import {
  createInOrder,
  createLiveTalkTurns,
  LIVE_TALK_USER_LINE_WAIT_MS,
  type LiveTalkTurn,
} from "@/features/speech/model/liveTalkTurns";

function call() {
  const saved: LiveTalkTurn[] = [];
  const turns = createLiveTalkTurns((turn) => saved.push(turn));
  /** The user's line, by the id the realtime event gives it. */
  const line = (turnId: string, text: string) => {
    const owner = turns.turnFor(turnId);
    if (owner) turns.user(owner, text);
    return owner;
  };
  return { turns, saved, line };
}

describe("live talk turns", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it("saves a turn as soon as its reply is done when the user's line is in", () => {
    const { turns, saved, line } = call();
    turns.utterance("u1");
    line("u1", "What is the capital of France?");
    turns.assistant("Paris.");
    turns.replied();
    expect(saved).toEqual([{ id: "u1", userText: "What is the capital of France?", assistantText: "Paris." }]);
  });

  // The line was transcribed after the reply ended: the turn was saved without it (and the
  // server keeps no reply without a line), and the line was saved as a turn of its own.
  it("waits for a line that lands after the reply, and saves the two together", () => {
    const { turns, saved, line } = call();
    turns.utterance("u1");
    turns.assistant("Yes.");
    turns.replied();
    jest.advanceTimersByTime(LIVE_TALK_USER_LINE_WAIT_MS - 1);
    expect(saved).toEqual([]);
    expect(line("u1", "Can you hear me?")).toBe("u1");
    expect(saved).toEqual([{ id: "u1", userText: "Can you hear me?", assistantText: "Yes." }]);
    expect(turns.current()).toBeNull();
  });

  it("saves the reply without a line once the wait ends, and a later line joins no turn", () => {
    const { turns, saved, line } = call();
    turns.utterance("u1");
    turns.assistant("Yes.");
    turns.replied();
    jest.advanceTimersByTime(LIVE_TALK_USER_LINE_WAIT_MS);
    expect(saved).toEqual([{ id: "u1", userText: "", assistantText: "Yes." }]);
    expect(line("u1", "Too late")).toBeNull();
    expect(saved).toHaveLength(1);
  });

  it("keeps waiting for a line after the next utterance began, and saves the turns in order", () => {
    const { turns, saved, line } = call();
    turns.utterance("u1");
    turns.assistant("Stopped");
    turns.replied();
    turns.utterance("u2");
    line("u2", "And Spain?");
    turns.assistant("Madrid.");
    turns.replied();
    // u2 is done, but u1 began first and still waits for its line.
    expect(saved).toEqual([]);
    line("u1", "What is the capital of France?");
    expect(saved.map((turn) => [turn.id, turn.userText])).toEqual([
      ["u1", "What is the capital of France?"],
      ["u2", "And Spain?"],
    ]);
  });

  it("saves a turn the next utterance cuts off before any reply", () => {
    const { turns, saved, line } = call();
    turns.utterance("u1");
    line("u1", "hello");
    turns.utterance("u2");
    expect(saved).toEqual([{ id: "u1", userText: "hello", assistantText: "" }]);
  });

  it("gives a line with no id to the turn being spoken, starting one if none is", () => {
    const { turns } = call();
    const owner = turns.turnFor();
    expect(owner).toEqual(expect.any(String));
    expect(turns.assistant("Hi")).toBe(owner);
  });

  it("hands every open turn on at once when the call ends, and nothing empty", () => {
    const { turns, saved, line } = call();
    turns.utterance("u1");
    turns.assistant("One.");
    turns.replied();
    turns.utterance("u2");
    line("u2", "two");
    turns.utterance("u3");
    turns.finishAll();
    expect(saved.map((turn) => turn.id)).toEqual(["u1", "u2"]);
    expect(jest.getTimerCount()).toBe(0);
  });
});

describe("the call's saves, in order", () => {
  it("starts each when the one before settles, a failed one included", async () => {
    const inOrder = createInOrder();
    const started: string[] = [];
    let finishFirst!: () => void;
    const first = inOrder(() => {
      started.push("first");
      return new Promise<void>((_resolve, reject) => {
        finishFirst = () => reject(new Error("refused"));
      });
    });
    const second = inOrder(async () => {
      started.push("second");
      return "saved";
    });
    await Promise.resolve();
    expect(started).toEqual(["first"]);
    finishFirst();
    await expect(first).rejects.toThrow("refused");
    await expect(second).resolves.toBe("saved");
    expect(started).toEqual(["first", "second"]);
  });
});
