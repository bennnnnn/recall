import { act, render } from "@testing-library/react-native";
import LearningSettingsScreen from "@/app/settings/learning";
let mockSession = 1;
let mockFocused = true;
const mockToken = "token";
const mockUpdate = jest.fn();
const mockExport = jest.fn();
const mockPrint = jest.fn();
const mockFeedback = { error: jest.fn() };
const mockRefresh = jest.fn();
const mockRouter = { push: jest.fn() };
const mockT = (key: string) => key;
let mockRows: any[];
let mockPicker: any;
let mockExportPress: () => void;
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: mockToken }) }));
jest.mock("@/contexts/ProjectsContext", () => ({
  useProjects: () => ({
    projects: mockRows,
    loading: false,
    error: false,
    refresh: mockRefresh,
    setProjects: (fn: any) => {
      mockRows = fn(mockRows);
    },
  }),
}));
jest.mock("@/hooks/useProjectActions", () => ({
  useProjectActions: () => ({ updateProject: mockUpdate, getExportProject: mockExport }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => mockFeedback,
}));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("react-native-safe-area-context", () => ({ useSafeAreaInsets: () => ({ bottom: 0 }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({}) }));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/components/StateView", () => ({ StateView: () => null }));
jest.mock("@/lib/exportProjectPdf", () => ({
  projectHasExportableItems: () => true,
  exportProjectAsPdf: (...args: unknown[]) => mockPrint(...args),
}));
jest.mock("@/lib/exportPdf", () => ({ isShareCancelled: () => false }));
jest.mock("@/components/settings/settingsUi", () => ({
  makeSettingsStyles: () => ({}),
  SettingsGroup: ({ children }: any) => children,
  SettingsInlinePicker: (props: any) => {
    mockPicker = props;
    return null;
  },
  SettingsLinkRow: ({ onPress }: any) => {
    mockExportPress = onPress;
    return null;
  },
}));
jest.mock("expo-router", () => ({
  Redirect: () => null,
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
  mockFocused = true;
  mockRows = [
    { id: "p", kind: "language", target_language: "es", title: "Spanish", daily_goal: 5 },
  ];
  mockRefresh.mockResolvedValue(undefined);
});
it("removes manual class deletion", async () => {
  const ui = await render(<LearningSettingsScreen />);
  expect(ui.queryByText("settings.learning.delete_class")).toBeNull();
});
it("rolls back only the goal while preserving concurrent class changes", async () => {
  let reject!: (error: Error) => void;
  mockUpdate.mockReturnValueOnce(
    new Promise((_, fail) => {
      reject = fail;
    }),
  );
  await render(<LearningSettingsScreen />);
  await act(() => {
    mockPicker.onSelect("10");
  });
  mockRows = mockRows.map((row) => ({ ...row, title: "New title", stats: { mastered_count: 4 } }));
  await act(async () => {
    reject(new Error("offline"));
  });
  expect(mockRows[0]).toMatchObject({
    title: "New title",
    daily_goal: 5,
    stats: { mastered_count: 4 },
  });
});
it("blocks retained goal callbacks immediately after account change", async () => {
  await render(<LearningSettingsScreen />);
  const select = mockPicker.onSelect;
  mockSession++;
  await act(() => {
    select("10");
  });
  expect(mockUpdate).not.toHaveBeenCalled();
});
it("does not open a PDF after leaving the screen", async () => {
  let resolve!: (value: unknown) => void;
  mockExport.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const ui = await render(<LearningSettingsScreen />);
  await act(() => {
    mockExportPress();
  });
  await ui.unmount();
  await act(async () => {
    resolve({ id: "p" });
  });
  expect(mockPrint).not.toHaveBeenCalled();
});
it("keeps a pending goal exclusive across a screen remount", async () => {
  let resolve!: (value: unknown) => void;
  mockUpdate.mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const ui = await render(<LearningSettingsScreen />);
  await act(() => {
    mockPicker.onSelect("10");
    mockPicker.onSelect("15");
  });
  await ui.unmount();
  await render(<LearningSettingsScreen />);
  expect(mockPicker.busy).toBe(true);
  await act(() => {
    mockPicker.onSelect("15");
  });
  expect(mockUpdate).toHaveBeenCalledTimes(1);
  await act(async () => {
    resolve({ daily_goal: 10 });
  });
  expect(mockPicker.busy).toBe(false);
});
it("does not roll a previous account's failed goal into the next account", async () => {
  let reject!: (error: Error) => void;
  mockUpdate.mockReturnValueOnce(
    new Promise((_, fail) => {
      reject = fail;
    }),
  );
  const ui = await render(<LearningSettingsScreen />);
  await act(() => {
    mockPicker.onSelect("10");
  });
  mockSession++;
  mockRows = [{ ...mockRows[0], title: "Other account", daily_goal: 15 }];
  await ui.rerender(<LearningSettingsScreen />);
  await act(async () => {
    reject(new Error("offline"));
  });
  expect(mockRows[0].daily_goal).toBe(15);
  expect(mockFeedback.error).not.toHaveBeenCalled();
});
