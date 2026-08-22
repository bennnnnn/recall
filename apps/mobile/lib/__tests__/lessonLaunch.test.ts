import { lessonPath, queueLessonLaunch, takeQueuedLessonLaunch } from "@/lib/lessonLaunch";

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
      }),
    ).toBe(true);
    expect(takeQueuedLessonLaunch()).toEqual({
      projectId: "proj-1",
      prompt: "Continue Spanish",
      quizVariant: "vocab",
    });
    expect(takeQueuedLessonLaunch()).toBeNull();
  });

  it("builds the lesson route", () => {
    expect(lessonPath("abc")).toBe("/projects/abc/lesson/play");
  });
});
