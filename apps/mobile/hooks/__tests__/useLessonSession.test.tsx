import React, { useLayoutEffect } from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { api, type ProjectDetail, type ProjectItem } from "@/lib/api";
import { useLessonSession } from "@/hooks/useLessonSession";
import { updateProjectDetailCache } from "@/lib/cache/projectDetailCache";
let mockSession = 1;
let mockToken = "token";
let mockFocused = true;
let mockUuid = 0;
const mockCurrent = () => mockFocused;
const mockT = (key: string, values?: Record<string, string>) =>
  `${key}:${values?.word ?? values?.sentence ?? ""}`;
const mockRefresh = jest.fn();
const mockLoad = jest.fn();
jest.mock("expo-crypto", () => ({ randomUUID: () => `attempt-${++mockUuid}` }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => mockToken }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/ProjectsContext", () => ({ useProjects: () => ({ refresh: mockRefresh }) }));
jest.mock("@/hooks/useProjectDetail", () => ({
  useProjectDetail: () => ({
    project: mockProject,
    loading: false,
    loadError: false,
    load: mockLoad,
    isCurrentOwner: mockCurrent,
  }),
}));
jest.mock("@/lib/api", () => ({ api: { recordProjectPractice: jest.fn() } }));
jest.mock("@/lib/cache/projectDetailCache", () => ({
  updateProjectDetailCache: jest.fn(),
  fetchProjectDetail: jest.fn(),
}));
const word = (id: string, content: string): ProjectItem => ({
  id,
  content,
  definition: `Meaning of ${content}`,
  example_sentence: `We say ${content}.`,
  list_title: "Start",
  status: "new",
  mastered: false,
  note: null,
  mastered_at: null,
  last_reviewed_at: null,
  review_count: 0,
  pronunciation_url: null,
  created_at: "2026-09-04",
});
let mockProject: ProjectDetail;
let current: ReturnType<typeof useLessonSession>;
function Probe() {
  const value = useLessonSession("p", mockCurrent);
  useLayoutEffect(() => {
    current = value;
  });
  return <Text>{value.step?.kind ?? "done"}</Text>;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
const record = jest.mocked(api.recordProjectPractice);
const correct = () => {
  const step = current.step;
  if (!step || step.kind === "teach" || !step.quiz.correct) throw new Error("Expected question");
  return step.quiz.correct;
};
const response = () => ({
  item: { ...word("one", "hello"), status: "mastered" as const, mastered: true },
  recorded: true,
  newly_mastered: true,
});
beforeEach(() => {
  jest.clearAllMocks();
  mockSession += 1;
  mockToken = "token";
  mockFocused = true;
  mockProject = {
    id: "p",
    up_next: "Start",
    daily_goal: 5,
    lists: [
      { list_title: "Start", items: [word("one", "hello")] },
      { list_title: "Other", items: [word("two", "goodbye")] },
    ],
  } as ProjectDetail;
  record.mockResolvedValue(response());
});
it("requires an assessment, serializes wrong answers, and completes only the final correct question", async () => {
  const pending = deferred<ReturnType<typeof response>>();
  record.mockReturnValueOnce(pending.promise);
  await render(<Probe />);
  expect(record).not.toHaveBeenCalled();
  await act(() => current.continueLesson());
  expect(record).not.toHaveBeenCalled();
  const answer = correct();
  const wrong = answer === "A" ? "B" : "A";
  await act(() => {
    current.submitLetter(wrong);
    current.submitLetter(answer);
  });
  expect(record).toHaveBeenCalledTimes(1);
  expect(current.canAdvance).toBe(false);
  await act(async () => pending.resolve(response()));
  await act(() => current.submitLetter(answer));
  expect(current.canAdvance).toBe(true);
  expect(record).toHaveBeenLastCalledWith(
    "token",
    "p",
    "one",
    expect.objectContaining({ was_correct: true, completes_word: false }),
  );
  await act(() => current.continueLesson());
  await act(() => current.submitLetter(correct()));
  expect(record).toHaveBeenLastCalledWith(
    "token",
    "p",
    "one",
    expect.objectContaining({ completes_word: true }),
  );
  expect(current.learned).toBe(1);
  await act(() => current.continueLesson());
  expect(current.complete).toBe(true);
});
it("keeps a failed answer and retries exactly the same attempt without accepting another choice", async () => {
  record.mockRejectedValueOnce(new Error("offline"));
  await render(<Probe />);
  await act(() => current.continueLesson());
  const letter = correct();
  await act(() => current.submitLetter(letter));
  expect(current.answer).toMatchObject({ letter, status: "failed" });
  expect(current.canAdvance).toBe(false);
  const attempt = record.mock.calls[0][3];
  await act(() => {
    current.submitLetter(letter);
    current.continueLesson();
  });
  expect(record).toHaveBeenCalledTimes(1);
  await act(() => current.retryAnswer());
  expect(record.mock.calls[1][3]).toEqual(attempt);
  expect(current.answer?.status).toBe("saved");
});
it("retains per-item exclusion across visits and publishes accepted same-account results after unmount", async () => {
  const pending = deferred<ReturnType<typeof response>>();
  record.mockReturnValueOnce(pending.promise);
  const first = await render(<Probe />);
  await act(() => current.continueLesson());
  await act(() => current.submitLetter(correct()));
  await first.unmount();
  const next = await render(<Probe />);
  await act(() => current.continueLesson());
  expect(current.saving).toBe(true);
  await act(() => current.submitLetter(correct()));
  expect(record).toHaveBeenCalledTimes(1);
  await act(async () => pending.resolve(response()));
  expect(updateProjectDetailCache).toHaveBeenCalledTimes(1);
  expect(current.saving).toBe(false);
  await act(() => current.submitLetter(correct()));
  expect(record).toHaveBeenCalledTimes(2);
  await next.unmount();
});
it("rejects retained callbacks and late results from a previous account", async () => {
  const pending = deferred<ReturnType<typeof response>>();
  record.mockReturnValueOnce(pending.promise);
  const screen = await render(<Probe />);
  await act(() => current.continueLesson());
  const oldSubmit = current.submitLetter;
  await act(() => current.submitLetter(correct()));
  mockSession += 1;
  mockToken = "other";
  await screen.rerender(<Probe />);
  await act(async () => {
    oldSubmit("A");
    pending.resolve(response());
  });
  expect(record).toHaveBeenCalledTimes(1);
  expect(updateProjectDetailCache).not.toHaveBeenCalled();
  expect(current.step?.kind).toBe("teach");
  expect(current.learned).toBe(0);
});
it("uses refreshed tokens while preserving the current question", async () => {
  const screen = await render(<Probe />);
  await act(() => current.continueLesson());
  mockToken = "refreshed";
  await screen.rerender(<Probe />);
  await act(() => current.submitLetter(correct()));
  expect(record.mock.calls[0][0]).toBe("refreshed");
});
it("does not record or advance from a blurred callback", async () => {
  await render(<Probe />);
  const next = current.continueLesson;
  mockFocused = false;
  await act(next);
  expect(current.step?.kind).toBe("teach");
  expect(record).not.toHaveBeenCalled();
});
it("counts a mastered chapter completion as reviewed", async () => {
  record.mockResolvedValue({ ...response(), newly_mastered: false });
  mockProject.lists[0].items[0].mastered = true;
  mockProject.lists[0].items[0].status = "mastered";
  await render(<Probe />);
  await act(() => current.continueLesson());
  await act(() => current.submitLetter(correct()));
  await act(() => current.continueLesson());
  await act(() => current.submitLetter(correct()));
  expect(current.reviewed).toBe(1);
  expect(current.learned).toBe(0);
});

it("can prepare an empty lesson after a successful content retry", async () => {
  const completeProject = mockProject;
  mockProject = { ...mockProject, lists: [] };
  const screen = await render(<Probe />);
  expect(current.empty).toBe(true);
  mockProject = completeProject;
  await screen.rerender(<Probe />);
  expect(current.empty).toBe(false);
  expect(current.step?.kind).toBe("teach");
});

it("uses the server outcome when a pending completion settles after a new visit seeded old content", async () => {
  const first = await render(<Probe />);
  await act(() => current.continueLesson());
  await act(() => current.submitLetter(correct()));
  await act(() => current.continueLesson());
  const pending = deferred<ReturnType<typeof response>>();
  record.mockReturnValueOnce(pending.promise);
  await act(() => current.submitLetter(correct()));
  await first.unmount();
  await render(<Probe />);
  expect(current.step?.kind).toBe("teach");
  await act(async () => pending.resolve(response()));
  record.mockResolvedValue({ ...response(), newly_mastered: false });
  await act(() => current.continueLesson());
  await act(() => current.submitLetter(correct()));
  await act(() => current.continueLesson());
  await act(() => current.submitLetter(correct()));
  expect(current.learned).toBe(0);
  expect(current.reviewed).toBe(1);
});
it("keeps original first-mastery classification when retry returns an idempotent replay", async () => {
  await render(<Probe />);
  await act(() => current.continueLesson());
  await act(() => current.submitLetter(correct()));
  await act(() => current.continueLesson());
  record.mockRejectedValueOnce(new Error("Lost response"));
  await act(() => current.submitLetter(correct()));
  const original = record.mock.calls.at(-1)?.[3];
  record.mockResolvedValue({ ...response(), recorded: false, newly_mastered: true });
  await act(() => current.retryAnswer());
  expect(record.mock.calls.at(-1)?.[3]).toEqual(original);
  expect(current.learned).toBe(1);
  expect(current.reviewed).toBe(0);
});
