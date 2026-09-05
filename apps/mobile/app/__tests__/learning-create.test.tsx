import { act, fireEvent, render } from "@testing-library/react-native";
import CreateLearningScreen from "@/app/projects/create";
let mockSession = 1;
let mockFocused = true;
let mockToken = "token";
let mockRows: any[];
let mockStep: any;
const mockCreate = jest.fn();
const mockRefresh = jest.fn();
const mockFeedback = { error: jest.fn() };
const mockRouter = { replace: jest.fn() };
const mockT = (key: string) => key;
const mockRedirect = jest.fn();
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: mockToken }) }));
jest.mock("@/contexts/ProjectsContext", () => ({
  useProjects: () => ({
    projects: mockRows,
    refresh: mockRefresh,
    setProjects: (fn: any) => {
      mockRows = fn(mockRows);
    },
  }),
}));
jest.mock("@/hooks/useProjectActions", () => ({
  useProjectActions: () => ({ createProject: mockCreate }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => mockFeedback,
}));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("react-native-safe-area-context", () => ({ useSafeAreaInsets: () => ({ bottom: 0 }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/components/projects/StepPicker", () => ({
  StepPicker: (props: any) => {
    mockStep = props;
    return null;
  },
}));
jest.mock("expo-router", () => ({
  Redirect: (props: any) => {
    mockRedirect(props);
    return null;
  },
  useRouter: () => mockRouter,
  useFocusEffect: (effect: any) => {
    const React = jest.requireActual("react");
    const focused = mockFocused;
    React.useEffect(() => (focused ? effect() : undefined), [effect, focused]);
  },
}));
beforeEach(() => {
  jest.clearAllMocks();
  mockSession = 1;
  mockToken = "token";
  mockFocused = true;
  mockRows = [];
  mockRefresh.mockResolvedValue(undefined);
});
async function start() {
  const ui = await render(<CreateLearningScreen />);
  await fireEvent.press(ui.getByText("English"));
  return ui;
}
it("deduplicates rapid creation and retains the second-class form while pending", async () => {
  mockRows = [{ id: "es", target_language: "es", kind: "language" }];
  let resolve!: (value: unknown) => void;
  mockCreate.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  await start();
  const submit = mockStep.onContinue;
  await act(() => {
    submit();
    submit();
  });
  expect(mockCreate).toHaveBeenCalledTimes(1);
  expect(mockRedirect).not.toHaveBeenCalled();
  await act(async () => {
    resolve({ id: "en", target_language: "en", kind: "language" });
  });
  expect(mockRows.map((row) => row.id)).toEqual(["en", "es"]);
});
it("does not publish or navigate for an old account's pending create", async () => {
  let resolve!: (value: unknown) => void;
  mockCreate.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const ui = await start();
  await act(() => {
    mockStep.onContinue();
  });
  mockSession++;
  mockRows = [];
  await ui.rerender(<CreateLearningScreen />);
  await act(async () => {
    resolve({ id: "old" });
  });
  expect(mockRows).toEqual([]);
  expect(mockRouter.replace).not.toHaveBeenCalled();
});
it("keeps same-account success after navigation without reopening the lesson", async () => {
  let resolve!: (value: unknown) => void;
  mockCreate.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const ui = await start();
  await act(() => {
    mockStep.onContinue();
  });
  await ui.unmount();
  await act(async () => {
    resolve({ id: "en", target_language: "en", kind: "language" });
  });
  expect(mockRows[0].id).toBe("en");
  expect(mockRouter.replace).not.toHaveBeenCalled();
});
it("rejects retained submit after blur and refocus", async () => {
  const ui = await start();
  const submit = mockStep.onContinue;
  mockFocused = false;
  await ui.rerender(<CreateLearningScreen />);
  mockFocused = true;
  await ui.rerender(<CreateLearningScreen />);
  await act(() => {
    submit();
  });
  expect(mockCreate).not.toHaveBeenCalled();
});
it("keeps creation current through a token refresh", async () => {
  let resolve!: (value: unknown) => void;
  mockCreate.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const ui = await start();
  await act(() => {
    mockStep.onContinue();
  });
  mockToken = "refreshed";
  await ui.rerender(<CreateLearningScreen />);
  await act(async () => {
    resolve({ id: "en", target_language: "en", kind: "language" });
  });
  expect(mockRouter.replace).toHaveBeenCalledWith("/projects/en/lesson");
});
it("removes only the failed optimistic class and requests authoritative recovery", async () => {
  let reject!: (error: Error) => void;
  mockCreate.mockReturnValueOnce(
    new Promise((_, fail) => {
      reject = fail;
    }),
  );
  await start();
  await act(() => {
    mockStep.onContinue();
  });
  mockRows.push({ id: "other", title: "Another class" });
  await act(async () => {
    reject(new Error("offline"));
  });
  expect(mockRows.map((row) => row.id)).toEqual(["other"]);
  expect(mockRefresh).toHaveBeenCalledWith({ silent: true, force: true, afterPending: true });
  expect(mockFeedback.error).toHaveBeenCalledWith("projects.create_failed");
});
