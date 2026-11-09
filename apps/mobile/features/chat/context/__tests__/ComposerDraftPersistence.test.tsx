import React from "react";
import { Pressable, Text } from "react-native";
import { act, fireEvent, render } from "@testing-library/react-native";

import { AccountSessionContext } from "@/contexts/accountSession";
import {
  ComposerDraftProvider,
  useComposerDraftApi,
  useComposerDraftValueOptional,
} from "@/features/chat/context/ComposerDraftContext";

// The account's drafts file, in memory: thread key -> text, by account.
const mockStored = new Map<string, Map<string, string>>();
const mockWrites: [string, Record<string, string>][] = [];
jest.mock("@/features/chat/model/composerDraftFile", () => ({
  readComposerDrafts: jest.fn(async (owner: string) => new Map(mockStored.get(owner) ?? [])),
  writeComposerDrafts: jest.fn(async (owner: string, drafts: Map<string, string>) => {
    const kept = new Map([...drafts].filter(([, text]) => text.trim()));
    mockStored.set(owner, kept);
    mockWrites.push([owner, Object.fromEntries(kept)]);
  }),
}));
const mockAppState: ((state: string) => void)[] = [];
jest.mock("@/lib/foregroundRefresh", () => ({
  onAppStateChange: (listener: (state: string) => void) => {
    mockAppState.push(listener);
    return () => undefined;
  },
}));

/** An access token for `sub` (only its claims are read, to name the account). */
function tokenFor(sub: string): string {
  return `h.${btoa(JSON.stringify({ sub })).replace(/=+$/, "")}.s`;
}

function Probe() {
  const draft = useComposerDraftValueOptional();
  const { setInput, typeInput, switchThread } = useComposerDraftApi();
  return (
    <>
      <Text testID="draft">{draft?.input ?? ""}</Text>
      <Pressable testID="type" onPress={() => typeInput("Plan a weekend in Rome")} />
      <Pressable testID="send" onPress={() => setInput("")} />
      <Pressable testID="to-chat-1" onPress={() => switchThread("chat-1")} />
    </>
  );
}

function App({ account = "user-1:1" }: { account?: string | null }) {
  const session = React.useMemo(
    () => ({ account, getToken: () => (account ? tokenFor(account.split(":")[0]!) : null) }),
    [account],
  );
  return (
    <AccountSessionContext.Provider value={session}>
      <ComposerDraftProvider>
        <Probe />
      </ComposerDraftProvider>
    </AccountSessionContext.Provider>
  );
}

beforeEach(() => {
  jest.useFakeTimers();
  mockStored.clear();
  mockWrites.length = 0;
  mockAppState.length = 0;
});
afterEach(() => jest.useRealTimers());

const settle = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

// The phone closing the app in the background took every unsent draft with it.
it("puts back the draft the last run left, for the chat it was typed in", async () => {
  mockStored.set("user-1", new Map([["new", "Plan a weekend"], ["chat-1", "and the hotel?"]]));
  const view = await render(<App />);
  await settle();
  expect(view.getByTestId("draft").props.children).toBe("Plan a weekend");

  await fireEvent.press(view.getByTestId("to-chat-1"));
  expect(view.getByTestId("draft").props.children).toBe("and the hotel?");
});

it("writes what is typed once typing settles, and at once when the app leaves the screen", async () => {
  const view = await render(<App />);
  await settle();
  await fireEvent.press(view.getByTestId("type"));
  expect(mockWrites).toEqual([]);
  await act(async () => { jest.advanceTimersByTime(1_000); });
  await settle();
  expect(mockStored.get("user-1")?.get("new")).toBe("Plan a weekend in Rome");

  mockWrites.length = 0;
  await fireEvent.press(view.getByTestId("to-chat-1"));
  await act(async () => { mockAppState.forEach((listener) => listener("background")); });
  await settle();
  expect(mockWrites.at(-1)).toEqual(["user-1", { new: "Plan a weekend in Rome" }]);
});

it("drops a draft once it is sent, without waiting", async () => {
  mockStored.set("user-1", new Map([["new", "Plan a weekend"]]));
  const view = await render(<App />);
  await settle();
  await fireEvent.press(view.getByTestId("send"));
  await settle();
  expect(mockStored.get("user-1")?.size).toBe(0);
});

// The file is read just after launch: a draft typed and sent (emptied) before it landed came back.
it("never brings back a draft this run emptied before the file was read", async () => {
  mockStored.set("user-1", new Map([["new", "Plan a weekend"]]));
  const { readComposerDrafts } = jest.requireMock("@/features/chat/model/composerDraftFile") as {
    readComposerDrafts: jest.Mock;
  };
  let land!: () => void;
  readComposerDrafts.mockImplementationOnce((owner: string) => new Promise((resolve) => {
    land = () => resolve(new Map(mockStored.get(owner) ?? []));
  }));
  const view = await render(<App />);
  await fireEvent.press(view.getByTestId("type"));
  await fireEvent.press(view.getByTestId("send"));
  await act(async () => { land(); });
  await settle();
  expect(view.getByTestId("draft").props.children).toBe("");
  await act(async () => { mockAppState.forEach((listener) => listener("background")); });
  await settle();
  expect(mockWrites.at(-1)).toEqual(["user-1", {}]);
});

it("reads and writes nothing while no one is signed in", async () => {
  mockStored.set("user-1", new Map([["new", "Plan a weekend"]]));
  const view = await render(<App account={null} />);
  await settle();
  await fireEvent.press(view.getByTestId("type"));
  await act(async () => { jest.advanceTimersByTime(1_000); });
  expect(view.getByTestId("draft").props.children).toBe("Plan a weekend in Rome");
  expect(mockWrites).toEqual([]);
});
