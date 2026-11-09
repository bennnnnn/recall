import { StyleSheet } from "react-native";
import { act, fireEvent, render, screen } from "@testing-library/react-native";

import { HomeStarters } from "@/features/home/components/HomeStarters";
import { AA, compositeOver, contrastRatio, SCHEME_ACCENTS } from "@/lib/__tests__/support/contrast";
import { DEFAULT_ACCENT } from "@/lib/accent";
import { setAccentSnapshot } from "@/lib/accentRuntime";
import { themeFor } from "@/lib/theme";

let mockOverdue: { id: string; content: string; due_at: string } | undefined;
let mockScheme: "light" | "dark" = "light";

jest.mock("@/lib/colorScheme", () => ({ useResolvedColorScheme: () => mockScheme }));

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: "user-1", reminder_lead_minutes: 15 } }),
}));
jest.mock("@/features/todos/context/TodosContext", () => ({
  useTodos: () => ({
    todos: [],
    loading: false,
    remindersReady: true,
    homeNudgeDismissed: new Set<string>(),
    dismissReminderNudge: jest.fn(),
  }),
}));
jest.mock("@/features/home/model/homeWelcome", () => ({
  homeGreeting: () => ({ hello: "Hi, Bini", question: "What are you working on?" }),
}));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("@/features/todos/model/dueDate", () => ({
  describeDueAt: () => ({ label: "2d overdue", tone: "overdue" }),
}));
jest.mock("@/features/todos/model/homeUrgentTodos", () => ({
  firstOverdueHomeTodo: () => mockOverdue,
}));
jest.mock("expo-router", () => ({ useRouter: () => ({ push: jest.fn() }) }));

beforeEach(() => {
  mockOverdue = undefined;
  jest.clearAllMocks();
});

afterEach(async () => {
  mockScheme = "light";
  await act(async () => setAccentSnapshot(DEFAULT_ACCENT));
});

it("shows the greeting without starter chips", async () => {
  const view = await render(<HomeStarters composerActive={false} />);
  expect(await view.findByText("Hi, Bini")).toBeTruthy();
  expect(view.queryByText("Help me think")).toBeNull();
  expect(view.queryByText("What can you do?")).toBeNull();
});

it("greets in two lines at the top: hi in the accent, the question in grey; no icon or subtitle", async () => {
  const view = await render(<HomeStarters composerActive={false} />);
  const greeting = await view.findByRole("header");
  expect(greeting.props.accessibilityLabel).toBe("Hi, Bini. What are you working on?");
  expect(view.getByText("What are you working on?")).toBeTruthy();
  expect(view.queryByText("chat.home.subtitle")).toBeNull();
  expect(view.queryByText("app.name")).toBeNull();
  const root = screen.root;
  if (!root) throw new Error("nothing rendered");
  expect(root.queryAll((node) => node.props.source != null)).toHaveLength(0);
  // Pinned to the top: centred in the free space, it jumped when the keyboard opened. The
  // greeting is the home's first child, and nothing above it centres or pushes it down.
  const home = greeting.parent;
  expect(home?.children[0]).toBe(greeting);
  for (let node = home; node; node = node.parent) {
    expect(StyleSheet.flatten(node.props.style ?? {}).justifyContent).not.toBe("center");
  }
});

/** WCAG 1.4.3: the greeting is large text (32pt semibold), 3:1 on the page. */
const LARGE_TEXT = 3;

it.each(SCHEME_ACCENTS)("%s %s: both lines read 3:1 on the page", async (scheme, accent) => {
  mockScheme = scheme;
  await act(async () => setAccentSnapshot(accent));
  const failures: string[] = [];
  const C = themeFor(scheme, accent);
  const ui = await render(<HomeStarters composerActive={false} />);
  const ink = (words: string) => String(StyleSheet.flatten(ui.getByText(words).props.style).color);
  expect({ hello: ink("Hi, Bini"), question: ink("What are you working on?") })
    .toEqual({ hello: C.primary, question: C.textTertiary });
  for (const [what, fg] of [["hello", C.primary], ["question", C.textTertiary]] as const) {
    const ratio = contrastRatio(fg, C.bg);
    if (ratio < LARGE_TEXT) failures.push(`${what} ${ratio.toFixed(2)}`);
  }
  await ui.unmount();
  expect(failures).toEqual([]);
});

it("hides the greeting while the composer is in use", async () => {
  const view = await render(<HomeStarters composerActive={false} />);
  expect(await view.findByText("Hi, Bini")).toBeTruthy();

  await view.rerender(<HomeStarters composerActive />);

  expect(view.queryByText("Hi, Bini")).toBeNull();
});

it("keeps one overdue reminder", async () => {
  mockOverdue = {
    id: "todo-1",
    content: "Pay rent",
    due_at: "2026-07-01T12:00:00.000Z",
  };
  const view = await render(<HomeStarters composerActive={false} />);
  expect(await view.findByText("Pay rent")).toBeTruthy();
  expect(view.getByText("chat.home.overdue")).toBeTruthy();
  await act(async () => {
    fireEvent.press(view.getByLabelText("chat.home.dismiss_reminder"));
  });
});

/** WCAG 1.4.11: an icon that carries meaning needs 3:1 on its plane. */
const NON_TEXT = 3;

// Red like the to-do row's overdue time and mark. Its heading sits on the chat page (bg);
// the rest on the card's own fill, laid over that page.
it.each(SCHEME_ACCENTS)(
  "%s %s: the overdue card is danger, AA for its text and 3:1 for its icons",
  async (scheme, accent) => {
    mockScheme = scheme;
    mockOverdue = { id: "todo-1", content: "Pay rent", due_at: "2026-07-01T12:00:00.000Z" };
    await act(async () => setAccentSnapshot(accent));
    const failures: string[] = [];
    const C = themeFor(scheme, accent);
    const ui = await render(<HomeStarters composerActive={false} />);
    const card = ui.getByLabelText("Pay rent");
    const cardStyle = StyleSheet.flatten(card.props.style);
    const plane = compositeOver(String(cardStyle.backgroundColor), C.bg);
    const ink = (node: ReturnType<typeof ui.getByText>) => String(StyleSheet.flatten(node.props.style).color);
    const heading = ink(ui.getByText("chat.home.overdue"));
    const due = ink(ui.getByText("2d overdue"));
    const icons = card.queryAll((node) => typeof node.props.name === "string");
    expect({ heading, due, border: cardStyle.borderColor, icons: icons.map((icon) => icon.props.color) })
      .toEqual({ heading: C.danger, due: C.danger, border: C.danger, icons: [C.danger, C.danger] });
    const pairs: [string, string, string, number][] = [
      ["heading", heading, C.bg, AA],
      ["title", ink(ui.getByText("Pay rent")), plane, AA],
      ["due", due, plane, AA],
      ...icons.map((icon): [string, string, string, number] => [icon.props.name, icon.props.color, plane, NON_TEXT]),
    ];
    for (const [what, fg, bg, floor] of pairs) {
      const ratio = contrastRatio(fg, bg);
      if (ratio < floor) failures.push(`${what} ${ratio.toFixed(2)}`);
    }
    await ui.unmount();
    expect(failures).toEqual([]);
  },
);
