import { act, fireEvent, render } from "@testing-library/react-native";

import { HomeStarters } from "@/features/home/components/HomeStarters";

let mockComposerActive = false;
let mockOverdue: { id: string; content: string; due_at: string } | undefined;

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "user-1", reminder_lead_minutes: 15 } }),
}));
jest.mock("@/contexts/ComposerDraftContext", () => ({
  useComposerDraftActivity: () => mockComposerActive,
}));
jest.mock("@/features/home/context/HomeContext", () => ({
  useHome: () => ({ screen: { greeting: "Good morning" } }),
}));
jest.mock("@/features/todos/context/TodosContext", () => ({
  useTodos: () => ({
    todos: [],
    loading: false,
    remindersReady: true,
    homeNudgeDismissed: {},
    dismissReminderNudge: jest.fn(),
  }),
}));
jest.mock("@/features/home/model/homeWelcome", () => ({
  instantHomePlaceholder: () => ({ greeting: "Hello" }),
}));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("@/features/todos/model/dueDate", () => ({
  describeDueAt: () => ({ label: "2d overdue", tone: "overdue" }),
}));
jest.mock("@/features/todos/model/homeReminderNudges", () => ({
  filterHomeNudgeTodos: (todos: unknown[]) => todos,
}));
jest.mock("@/features/todos/model/homeUrgentTodos", () => ({
  firstOverdueHomeTodo: () => mockOverdue,
  listHomeUrgentTodos: () => [],
}));
jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

beforeEach(() => {
  mockComposerActive = false;
  mockOverdue = undefined;
  jest.clearAllMocks();
});

it("shows the greeting without starter chips", async () => {
  const view = await render(<HomeStarters />);
  expect(await view.findByText("Good morning")).toBeTruthy();
  expect(view.queryByText("Help me think")).toBeNull();
  expect(view.queryByText("What can you do?")).toBeNull();
});

it("hides the greeting while the composer is in use", async () => {
  const view = await render(<HomeStarters />);
  expect(await view.findByText("Good morning")).toBeTruthy();

  mockComposerActive = true;
  await view.rerender(<HomeStarters />);

  expect(view.queryByText("Good morning")).toBeNull();
});

it("keeps one overdue reminder", async () => {
  mockOverdue = {
    id: "todo-1",
    content: "Pay rent",
    due_at: "2026-07-01T12:00:00.000Z",
  };
  const view = await render(<HomeStarters />);
  expect(await view.findByText("Pay rent")).toBeTruthy();
  expect(view.getByText("chat.home.overdue")).toBeTruthy();
  await act(async () => {
    fireEvent.press(view.getByLabelText("chat.home.dismiss_reminder"));
  });
});
