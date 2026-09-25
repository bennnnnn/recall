import { act, render } from "@testing-library/react-native";
import { LessonMapOverflowMenu } from "@/features/learning/components/LessonMapOverflowMenu";

let mockSession = 1;
const mockToken = "token";
const mockUpdate = jest.fn();
const mockExport = jest.fn();
const mockPrint = jest.fn();
const mockFeedback = { error: jest.fn(), info: jest.fn(), dismiss: jest.fn() };
const mockT = (key: string) => key;
type MockItem = { key: string; label: string; onPress: () => void; disabled?: boolean };
type MockMenu = { items: (MockItem | "separator")[]; testID?: string };
let mockMain: MockMenu;
let mockGoal: MockMenu;
const row = (menu: MockMenu, key: string) =>
  menu.items.find((item): item is MockItem => item !== "separator" && item.key === key)!;
// The two popovers' rows stand in for the old inline picker and link row.
const mockPicker = {
  onSelect: (key: string) => row(mockGoal, key).onPress(),
  get busy() {
    return Boolean(row(mockMain, "goal").disabled);
  },
};
const mockExportPress = () => row(mockMain, "export").onPress();
let isCurrentNow = true;
const mockCurrent = () => isCurrentNow;
const project = {
  id: "p",
  kind: "language" as const,
  target_language: "es",
  title: "Spanish",
  daily_goal: 5,
};

jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ token: mockToken }) }));
jest.mock("@/features/learning/hooks/useProjectActions", () => ({
  useProjectActions: () => ({ updateProject: mockUpdate, getExportProject: mockExport }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => mockFeedback,
}));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({ primary: "#000" }) }));
jest.mock("@/features/learning/model/exportProjectPdf", () => ({
  projectHasExportableItems: () => true,
  exportProjectAsPdf: (...args: unknown[]) => mockPrint(...args),
}));
jest.mock("@/lib/exportPdf", () => ({ isShareCancelled: () => false }));
jest.mock("@/ui/overlay/Menu", () => ({
  Menu: (props: MockMenu) => {
    if (props.testID === "lesson-goal-menu") mockGoal = props;
    else mockMain = props;
    return null;
  },
}));
jest.mock("@/ui/overlay/dialogs", () => ({ alert: jest.fn() }));

const menuProps = { visible: true, anchorRef: { current: null }, onClose: jest.fn() };

beforeEach(() => {
  jest.clearAllMocks();
  mockSession = 1;
  isCurrentNow = true;
  project.daily_goal = 5;
  mockUpdate.mockReset();
  mockExport.mockReset();
  mockPrint.mockReset();
});

it("offers words per day and Export PDF, and no manual class deletion", async () => {
  await render(
    <LessonMapOverflowMenu project={project} isCurrent={mockCurrent} {...menuProps} />,
  );
  const labels = mockMain.items.map((item) => (item === "separator" ? "-" : item.label));
  expect(labels).toEqual(["settings.learning.words_label", "settings.learning.export_pdf"]);
  expect(labels).not.toContain("settings.learning.delete_class");
});

it("rolls the daily goal back when the save fails", async () => {
  let reject!: (error: Error) => void;
  mockUpdate.mockReturnValueOnce(
    new Promise((_, fail) => {
      reject = fail;
    }),
  );
  await render(<LessonMapOverflowMenu project={project} isCurrent={mockCurrent} {...menuProps} />);
  await act(() => {
    mockPicker.onSelect("10");
  });
  await act(async () => {
    reject(new Error("offline"));
  });
  expect(mockPicker.busy).toBe(false);
});

it("blocks retained goal callbacks immediately after account change", async () => {
  await render(<LessonMapOverflowMenu project={project} isCurrent={mockCurrent} {...menuProps} />);
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
  const ui = await render(
    <LessonMapOverflowMenu project={project} isCurrent={mockCurrent} {...menuProps} />,
  );
  await act(() => {
    mockExportPress();
  });
  isCurrentNow = false;
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
  const ui = await render(
    <LessonMapOverflowMenu project={project} isCurrent={mockCurrent} {...menuProps} />,
  );
  await act(() => {
    mockPicker.onSelect("10");
    mockPicker.onSelect("15");
  });
  await ui.unmount();
  await render(<LessonMapOverflowMenu project={project} isCurrent={mockCurrent} {...menuProps} />);
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

it("does not apply a previous account's failed goal to the next account", async () => {
  let reject!: (error: Error) => void;
  mockUpdate.mockReturnValueOnce(
    new Promise((_, fail) => {
      reject = fail;
    }),
  );
  const ui = await render(
    <LessonMapOverflowMenu project={project} isCurrent={mockCurrent} {...menuProps} />,
  );
  await act(() => {
    mockPicker.onSelect("10");
  });
  mockSession++;
  await ui.rerender(
    <LessonMapOverflowMenu project={{ ...project, daily_goal: 15 }} isCurrent={mockCurrent} {...menuProps} />,
  );
  await act(async () => {
    reject(new Error("offline"));
  });
  expect(mockFeedback.error).not.toHaveBeenCalled();
});
