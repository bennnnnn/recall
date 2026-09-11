import { act, render } from "@testing-library/react-native";
import { LessonMapOverflowMenu } from "@/app/projects/[id]/lesson/LessonMapOverflowMenu";

let mockSession = 1;
const mockToken = "token";
const mockUpdate = jest.fn();
const mockExport = jest.fn();
const mockPrint = jest.fn();
const mockFeedback = { error: jest.fn() };
const mockT = (key: string) => key;
let mockPicker: { onSelect: (key: string) => void; busy?: boolean };
let mockExportPress: () => void;
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
jest.mock("@/hooks/useProjectActions", () => ({
  useProjectActions: () => ({ updateProject: mockUpdate, getExportProject: mockExport }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => mockFeedback,
}));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: mockT }) }));
jest.mock("@/lib/theme", () => ({ useTheme: () => ({ primary: "#000" }) }));
jest.mock("@/lib/exportProjectPdf", () => ({
  projectHasExportableItems: () => true,
  exportProjectAsPdf: (...args: unknown[]) => mockPrint(...args),
}));
jest.mock("@/lib/exportPdf", () => ({ isShareCancelled: () => false }));
jest.mock("@/components/settings/settingsUi", () => ({
  makeSettingsStyles: () => ({}),
  SettingsGroup: ({ children }: { children: unknown }) => children,
  SettingsInlinePicker: (props: { onSelect: (key: string) => void; busy?: boolean }) => {
    mockPicker = props;
    return null;
  },
  SettingsLinkRow: ({ onPress }: { onPress: () => void }) => {
    mockExportPress = onPress;
    return null;
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockSession = 1;
  isCurrentNow = true;
  project.daily_goal = 5;
  mockUpdate.mockReset();
  mockExport.mockReset();
  mockPrint.mockReset();
});

it("removes manual class deletion", async () => {
  const ui = await render(
    <LessonMapOverflowMenu project={project} isCurrent={mockCurrent} />,
  );
  expect(ui.queryByText("settings.learning.delete_class")).toBeNull();
});

it("rolls the daily goal back when the save fails", async () => {
  let reject!: (error: Error) => void;
  mockUpdate.mockReturnValueOnce(
    new Promise((_, fail) => {
      reject = fail;
    }),
  );
  await render(<LessonMapOverflowMenu project={project} isCurrent={mockCurrent} />);
  await act(() => {
    mockPicker.onSelect("10");
  });
  await act(async () => {
    reject(new Error("offline"));
  });
  expect(mockPicker).toMatchObject({ busy: false });
});

it("blocks retained goal callbacks immediately after account change", async () => {
  await render(<LessonMapOverflowMenu project={project} isCurrent={mockCurrent} />);
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
    <LessonMapOverflowMenu project={project} isCurrent={mockCurrent} />,
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
    <LessonMapOverflowMenu project={project} isCurrent={mockCurrent} />,
  );
  await act(() => {
    mockPicker.onSelect("10");
    mockPicker.onSelect("15");
  });
  await ui.unmount();
  await render(<LessonMapOverflowMenu project={project} isCurrent={mockCurrent} />);
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
    <LessonMapOverflowMenu project={project} isCurrent={mockCurrent} />,
  );
  await act(() => {
    mockPicker.onSelect("10");
  });
  mockSession++;
  await ui.rerender(
    <LessonMapOverflowMenu project={{ ...project, daily_goal: 15 }} isCurrent={mockCurrent} />,
  );
  await act(async () => {
    reject(new Error("offline"));
  });
  expect(mockFeedback.error).not.toHaveBeenCalled();
});
