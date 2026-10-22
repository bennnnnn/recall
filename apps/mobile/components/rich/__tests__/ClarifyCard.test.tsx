import { fireEvent, render } from "@testing-library/react-native";
import type { ReactNode } from "react";

import { ClarifyCard } from "@/components/rich/ClarifyCard";
import { ClarifyActionsProvider, ClarifyMessageScope } from "@/components/rich/clarifyContext";
import { ReplyStreaming } from "@/components/markdown/ReplyStreaming";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: {
    t: (key: string, options?: Record<string, string>) =>
      options ? `${key}|${Object.values(options).join("|")}` : key,
  },
}));
jest.mock("@/lib/haptics", () => ({ selection: jest.fn() }));
jest.mock("@/ui/icons/Icon", () => ({ Icon: () => null }));

const INTEGRALS = JSON.stringify({
  when: "first",
  questions: [
    {
      id: "level",
      label: "Studied it before",
      question: "Have you studied integrals before?",
      options: ["No, never", "A little", "Yes, I'm revising"],
      multi: false,
    },
    {
      id: "goal",
      label: "What it's for",
      question: "What do you need it for?",
      options: ["An exam", "A class", "Curiosity"],
      multi: false,
    },
  ],
});

const LAPTOP = JSON.stringify({
  when: "first",
  questions: [
    {
      id: "use",
      label: "Used for",
      question: "What will you use it for?",
      options: ["Games", "Work", "Study"],
      multi: true,
    },
  ],
});

type Setup = {
  content?: string;
  latest?: boolean;
  nextUserText?: string | null;
  busy?: boolean;
  streaming?: boolean;
  provider?: boolean;
};

async function setup({
  content = INTEGRALS,
  latest = true,
  nextUserText = null,
  busy = false,
  streaming = false,
  provider = true,
}: Setup = {}) {
  const send = jest.fn();
  let tree: ReactNode = (
    <ClarifyMessageScope latest={latest} nextUserText={nextUserText}>
      <ReplyStreaming value={streaming}>
        <ClarifyCard content={content} />
      </ReplyStreaming>
    </ClarifyMessageScope>
  );
  if (provider) {
    tree = (
      <ClarifyActionsProvider send={send} busy={busy}>
        {tree}
      </ClarifyActionsProvider>
    );
  }
  const view = await render(<>{tree}</>);
  return { view, send };
}

function checked(view: Awaited<ReturnType<typeof setup>>["view"], label: string): boolean {
  return view.getByRole(/radio|checkbox/, { name: label }).props.accessibilityState?.checked === true;
}

describe("ClarifyCard", () => {
  it("shows every question with its choices and Other…", async () => {
    const { view } = await setup();
    expect(view.getByText("Have you studied integrals before?")).toBeTruthy();
    expect(view.getByText("Yes, I'm revising")).toBeTruthy();
    expect(view.getAllByText("clarify.other")).toHaveLength(2);
    expect(view.getByText("clarify.badge")).toBeTruthy();
  });

  it("sends the picks as one Label: pick line per question", async () => {
    const { view, send } = await setup();
    await fireEvent.press(view.getByText("clarify.submit"));
    expect(send).not.toHaveBeenCalled();
    await fireEvent.press(view.getByText("No, never"));
    await fireEvent.press(view.getByText("clarify.submit"));
    expect(send).not.toHaveBeenCalled();
    await fireEvent.press(view.getByText("An exam"));
    await fireEvent.press(view.getByText("clarify.submit"));
    expect(send).toHaveBeenCalledWith("Studied it before: No, never\nWhat it's for: An exam");
  });

  it("lets a single-choice question change its pick", async () => {
    const { view } = await setup();
    await fireEvent.press(view.getByText("A little"));
    await fireEvent.press(view.getByText("No, never"));
    expect(checked(view, "No, never")).toBe(true);
    expect(checked(view, "A little")).toBe(false);
  });

  it("joins several picks on a multi-choice question", async () => {
    const { view, send } = await setup({ content: LAPTOP });
    await fireEvent.press(view.getByText("Study"));
    await fireEvent.press(view.getByText("Games"));
    await fireEvent.press(view.getByText("Work"));
    await fireEvent.press(view.getByText("Work"));
    await fireEvent.press(view.getByText("clarify.submit"));
    expect(send).toHaveBeenCalledWith("Used for: Games, Study");
  });

  it("opens a field for Other… and sends the typed answer", async () => {
    const { view, send } = await setup();
    const [levelOther] = view.getAllByText("clarify.other");
    await fireEvent.press(levelOther!);
    const field = view.getByPlaceholderText("clarify.other_placeholder");
    await fireEvent.press(view.getByText("A class"));
    await fireEvent.press(view.getByText("clarify.submit"));
    expect(send).not.toHaveBeenCalled();
    await fireEvent.changeText(field, "Years ago,\nin school");
    await fireEvent.press(view.getByText("clarify.submit"));
    expect(send).toHaveBeenCalledWith("Studied it before: Years ago, in school\nWhat it's for: A class");
  });

  it("sends Just answer on Skip", async () => {
    const { view, send } = await setup();
    await fireEvent.press(view.getByText("clarify.skip"));
    expect(send).toHaveBeenCalledWith("clarify.skip_message");
  });

  it("sends once, then stays read-only with the picks ticked", async () => {
    const { view, send } = await setup();
    await fireEvent.press(view.getByText("A little"));
    await fireEvent.press(view.getByText("Curiosity"));
    await fireEvent.press(view.getByText("clarify.submit"));
    expect(send).toHaveBeenCalledTimes(1);
    expect(view.queryByText("clarify.submit")).toBeNull();
    expect(view.queryByText("clarify.skip")).toBeNull();
    expect(checked(view, "A little")).toBe(true);
    await fireEvent.press(view.getByText("No, never"));
    expect(checked(view, "No, never")).toBe(false);
  });

  it("ticks the picks a later message sent, read-only", async () => {
    const { view, send } = await setup({
      latest: false,
      nextUserText: "Studied it before: Yes, I'm revising\nWhat it's for: my own project",
    });
    expect(view.queryByText("clarify.submit")).toBeNull();
    expect(checked(view, "Yes, I'm revising")).toBe(true);
    expect(view.getByText("clarify.other_answer|my own project")).toBeTruthy();
    await fireEvent.press(view.getByText("No, never"));
    expect(send).not.toHaveBeenCalled();
  });

  it("is read-only after a skip, with nothing ticked", async () => {
    const { view } = await setup({ nextUserText: "Just answer" });
    expect(view.queryByText("clarify.submit")).toBeNull();
    expect(checked(view, "No, never")).toBe(false);
  });

  it.each([
    ["on an older reply", { latest: false }],
    ["while a reply is streaming or saving", { busy: true }],
    ["while its own reply is still streaming", { streaming: true }],
    ["outside a chat", { provider: false }],
  ])("cannot be answered %s", async (_name, options) => {
    const { view, send } = await setup(options);
    expect(view.queryByText("clarify.submit")).toBeNull();
    await fireEvent.press(view.getByText("No, never"));
    expect(checked(view, "No, never")).toBe(false);
    expect(send).not.toHaveBeenCalled();
  });

  it("never shows a broken card's JSON", async () => {
    const { view } = await setup({ content: '{"questions": [{"question": "Which?"' });
    expect(view.toJSON()).toBeNull();
  });

  it("shows a card written as plain text as text", async () => {
    const { view } = await setup({ content: "Have you studied integrals before?" });
    expect(view.getByText("Have you studied integrals before?")).toBeTruthy();
  });
});
