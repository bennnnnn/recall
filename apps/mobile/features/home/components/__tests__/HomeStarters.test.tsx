import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

import { HomeStarters } from "@/features/home/components/HomeStarters";
import { retireHomeGuidance } from "@/features/home/model/homeGuidancePrefs";

let mockComposerActive = false;
let mockRetired = false;

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
jest.mock("@/features/home/model/homeGuidancePrefs", () => ({
  isHomeGuidanceRetired: jest.fn(async () => mockRetired),
  retireHomeGuidance: jest.fn(async () => undefined),
}));
jest.mock("@/features/home/model/homeWelcome", () => ({
  instantHomePlaceholder: () => ({ greeting: "Hello" }),
  welcomeStarterIcon: () => "sparkles-outline",
  welcomeStarters: () => [
    { text: "Help me think", prompt: "Help me think through something", kind: "general" },
  ],
}));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("@/features/todos/model/dueDate", () => ({ describeDueAt: () => null }));
jest.mock("@/features/todos/model/homeReminderNudges", () => ({
  filterHomeNudgeTodos: (todos: unknown[]) => todos,
}));
jest.mock("@/features/todos/model/homeUrgentTodos", () => ({
  firstOverdueHomeTodo: () => undefined,
  listHomeUrgentTodos: () => [],
}));
jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn() }) }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

beforeEach(() => {
  mockComposerActive = false;
  mockRetired = false;
  jest.clearAllMocks();
});

it("retires starter guidance as soon as typing starts", async () => {
  const view = await render(<HomeStarters onSelect={jest.fn()} />);
  expect(await view.findByText("Good morning")).toBeTruthy();

  mockComposerActive = true;
  await view.rerender(<HomeStarters onSelect={jest.fn()} />);

  expect(view.queryByText("Good morning")).toBeNull();
  expect(view.queryByLabelText("Help me think")).toBeNull();
  await waitFor(() => {
    expect(retireHomeGuidance).toHaveBeenCalledWith("user-1");
  });

  mockComposerActive = false;
  await view.rerender(<HomeStarters onSelect={jest.fn()} />);

  expect(view.queryByLabelText("Help me think")).toBeNull();
});

it("retires a starter immediately when it is tapped", async () => {
  const onSelect = jest.fn();
  const view = await render(<HomeStarters onSelect={onSelect} />);
  const chip = await view.findByLabelText("Help me think");

  await act(async () => {
    fireEvent.press(chip);
  });

  expect(view.queryByLabelText("Help me think")).toBeNull();
  expect(retireHomeGuidance).toHaveBeenCalledWith("user-1");
  expect(onSelect).toHaveBeenCalledWith("Help me think through something", undefined);
});

it("keeps starter chips hidden for an account that already used chat", async () => {
  mockRetired = true;
  const view = await render(<HomeStarters onSelect={jest.fn()} />);

  expect(await view.findByText("Good morning")).toBeTruthy();
  expect(view.queryByLabelText("Help me think")).toBeNull();
});
