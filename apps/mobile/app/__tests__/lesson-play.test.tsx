import React from "react";
import { act, fireEvent, render } from "@testing-library/react-native";
import LessonPlay from "@/app/projects/[id]/lesson/play";
import { api } from "@/lib/api";
const mockRouter = { replace: jest.fn() };
const mockCurrent = () => true;
const mockRefresh = jest.fn();
const mockLoad = jest.fn();
let mockId = 0;
const mockProject = {
  id: "p",
  kind: "language",
  target_language: "es",
  up_next: "Morning",
  daily_goal: 5,
  lists: [
    {
      list_title: "Morning",
      items: [
        {
          id: "one",
          content: "despertarse",
          definition: "Dejar de dormir.",
          example_sentences: ["Me despierto a las siete.", "Ana se despierta temprano."],
          status: "new",
          mastered: false,
          verb_kind: "action",
        },
      ],
    },
    {
      list_title: "Other",
      items: [
        {
          id: "two",
          content: "dormir",
          definition: "Descansar durante la noche.",
          status: "new",
          mastered: false,
        },
      ],
    },
  ],
};
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => mockRouter,
  useLocalSearchParams: () => ({ id: "p" }),
  useFocusEffect: (callback: () => void) =>
    jest.requireActual("react").useEffect(callback, [callback]),
}));
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: jest.requireActual("react-native").View,
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token", user: { id: "user" } }),
  useAuthToken: () => "token",
}));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
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
jest.mock("expo-crypto", () => ({ randomUUID: () => `attempt-${++mockId}` }));
jest.mock("@/lib/cache/projectDetailCache", () => ({
  updateProjectDetailCache: jest.fn(),
  fetchProjectDetail: jest.fn(),
}));
jest.mock("@/hooks/useLessonFeedback", () => ({
  useLessonFeedback: () => ({
    sound: true,
    voice: false,
    toggleSound: jest.fn(),
    toggleVoice: jest.fn(),
    speak: jest.fn(),
    stop: jest.fn(),
  }),
}));
jest.mock("@/lib/pronunciation", () => ({ speakWord: jest.fn() }));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
}));
jest.mock("@/lib/motion", () => ({ useReduceMotion: () => true }));
jest.mock("@/hooks/useResolvedColorScheme", () => ({ useResolvedColorScheme: () => "light" }));
jest.mock("@/components/ActionShimmer", () => ({
  ActionShimmer: ({ label }: { label: string }) =>
    jest.requireActual("react").createElement(jest.requireActual("react-native").Text, null, label),
}));
jest.mock("react-i18next", () => {
  const strings = require("@/lib/i18n/en.json");
  const t = (key: string, args: Record<string, unknown> = {}) =>
    String(strings[key] ?? key).replace(/{{(\w+)}}/g, (_: string, name: string) =>
      String(args[name] ?? ""),
    );
  return { useTranslation: () => ({ t, i18n: { language: "en" } }) };
});
it("mounts through actual focus ownership, teaches two examples, saves/retries assessment, and returns to the map", async () => {
  const record = jest.mocked(api.recordProjectPractice);
  record
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({
      item: mockProject.lists[0].items[0],
      recorded: true,
      newly_mastered: true,
    } as Awaited<ReturnType<typeof api.recordProjectPractice>>);
  const screen = await render(<LessonPlay />);
  expect(screen.getByText("Me despierto a las siete.")).toBeOnTheScreen();
  expect(screen.getByText("Ana se despierta temprano.")).toBeOnTheScreen();
  expect(record).not.toHaveBeenCalled();
  await fireEvent.press(screen.getByText("Continue"));
  await fireEvent.press(screen.getByText("Dejar de dormir."));
  expect(screen.getByText("Couldn't save your answer. Try again.")).toBeOnTheScreen();
  expect(screen.queryByText("Practice complete")).toBeNull();
  await fireEvent.press(screen.getByText("Retry"));
  expect(record.mock.calls[0][3]).toEqual(record.mock.calls[1][3]);
  expect(record.mock.calls[1][3]).toMatchObject({ was_correct: true, completes_word: true });
  await fireEvent.press(screen.getByText("Continue"));
  expect(screen.getByText("1 learned · 0 reviewed")).toBeOnTheScreen();
  await fireEvent.press(screen.getByText("Back to lesson map"));
  expect(mockRouter.replace).toHaveBeenCalledWith("/projects/p/lesson");
  await act(() => screen.unmount());
});
