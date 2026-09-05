import {
  peekQueuedLessonLaunch,
  lessonPath,
  queueLessonLaunch,
  takeQueuedLessonLaunch,
} from "@/lib/lessonLaunch";

let mockSession = 1;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));

it("drops a queued lesson on account changes", () => {
  queueLessonLaunch({ projectId: "old" });
  mockSession += 1;
  expect(peekQueuedLessonLaunch()).toBeNull();
  expect(takeQueuedLessonLaunch()).toBeNull();
});

describe("lessonLaunch", () => {
  beforeEach(() => {
    while (takeQueuedLessonLaunch()) {
      /* drain */
    }
  });

  it("rejects a blank project id", () => {
    expect(queueLessonLaunch({ projectId: "   " })).toBe(false);
    expect(takeQueuedLessonLaunch()).toBeNull();
  });

  it("queues a trimmed project and optional prompt", () => {
    expect(
      queueLessonLaunch({
        projectId: " proj-1 ",
        prompt: "  Continue Spanish  ",
        quizVariant: "vocab",
        chapter: "  Greetings  ",
      }),
    ).toBe(true);
    expect(takeQueuedLessonLaunch()).toEqual({
      projectId: "proj-1",
      prompt: "Continue Spanish",
      quizVariant: "vocab",
      chapter: "Greetings",
    });
    expect(takeQueuedLessonLaunch()).toBeNull();
  });

  it("builds the lesson route", () => {
    expect(lessonPath("abc")).toBe("/projects/abc/lesson/play");
  });
});
