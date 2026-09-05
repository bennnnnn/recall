import { act, fireEvent, render } from "@testing-library/react-native";

import LessonMap from "@/app/projects/[id]/lesson/index";
import { resetMapUnlockState } from "@/lib/projects/mapUnlock";

const mockPush = jest.fn();
const mockCurrent = () => true;
const mockLoad = jest.fn();
const mockOpen = jest.fn();

const mockProject = {
  id: "p",
  kind: "language",
  target_language: "en",
  up_next: "Morning",
  daily_goal: 5,
  stats: {
    completed_today: 5,
    mastered_today: 5,
    missed_today: 0,
  },
  path_progress: [
    {
      title: "Morning",
      domain: "Daily life",
      mastered: 4,
      total: 10,
      complete: false,
    },
    {
      title: "Night",
      domain: "Daily life",
      mastered: 0,
      total: 10,
      complete: false,
    },
  ],
};

jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
  useLocalSearchParams: () => ({ id: "p" }),
  useFocusEffect: (callback: () => void) =>
    jest.requireActual("react").useEffect(callback, [callback]),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token", user: { id: "user" } }),
  useAuthToken: () => "token",
}));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
jest.mock("@/hooks/useProjectDetail", () => ({
  useProjectDetail: () => ({
    project: mockProject,
    loading: false,
    loadError: false,
    load: mockLoad,
    isCurrentOwner: mockCurrent,
  }),
}));
jest.mock("@/lib/lessonLaunch", () => ({
  openLearningLesson: (...args: unknown[]) => mockOpen(...args),
}));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  notifySuccess: jest.fn(),
  notifyWarning: jest.fn(),
}));
jest.mock("@/lib/motion", () => ({
  useReduceMotion: () => true,
  Motion: {
    duration: { soft: 1, standard: 1 },
    easing: { inOut: undefined, out: undefined, in: undefined },
  },
}));
jest.mock("@/hooks/useResolvedColorScheme", () => ({
  useResolvedColorScheme: () => "light",
}));
jest.mock("react-i18next", () => {
  const strings = require("@/lib/i18n/en.json");
  const t = (key: string, args: Record<string, unknown> = {}) =>
    String(strings[key] ?? key).replace(/{{(\w+)}}/g, (_: string, name: string) =>
      String(args[name] ?? ""),
    );
  return { useTranslation: () => ({ t, i18n: { language: "en" } }) };
});

beforeEach(() => {
  resetMapUnlockState();
  mockOpen.mockReset();
});

it("opens the current group from the row, without a Next-lesson hero", async () => {
  const screen = await render(<LessonMap />);
  expect(screen.queryByText("Next lesson")).toBeNull();
  expect(screen.queryByText("Start practice")).toBeNull();
  expect(screen.getByText("Morning")).toBeOnTheScreen();
  expect(screen.getByText("Daily goal reached")).toBeOnTheScreen();
  await fireEvent.press(screen.getByText("Morning"));
  expect(mockOpen).toHaveBeenCalledWith(expect.anything(), {
    projectId: "p",
    chapter: "Morning",
  });
  await act(() => screen.unmount());
});
