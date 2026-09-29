import React from "react";
import { act, render, waitFor } from "@testing-library/react-native";

import { useChatSuggestions } from "@/features/suggestions/hooks/useChatSuggestions";
import { api, type Suggestion } from "@/lib/api";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/lib/cache/chatListCache", () => ({
  consumeCreatedSuggestionSkip: jest.fn(() => false),
}));
jest.mock("@/lib/reportRecoverableError", () => ({
  reportRecoverableError: jest.fn(),
}));
jest.mock("@/lib/api", () => ({
  api: {
    listSuggestions: jest.fn(),
    dismissSuggestion: jest.fn(),
  },
}));

function item(id: string, text: string): Suggestion {
  return {
    id,
    text,
    category: "followup",
    source: "chat",
    created_at: "2026-01-01T00:00:00.000Z",
  };
}

let latest: ReturnType<typeof useChatSuggestions> | null = null;

function Probe({
  hasMessages,
  turnBusy = false,
  refreshKey = 0,
}: {
  hasMessages: boolean;
  turnBusy?: boolean;
  refreshKey?: number;
}) {
  const result = useChatSuggestions({
    token: "token",
    chatId: "chat-1",
    hasMessages,
    turnBusy,
    refreshKey,
  });
  React.useLayoutEffect(() => {
    latest = result;
  });
  return null;
}

describe("useChatSuggestions", () => {
  beforeEach(() => {
    latest = null;
    jest.clearAllMocks();
  });

  it("loads at most three chips when an idle thread opens", async () => {
    (api.listSuggestions as jest.Mock).mockResolvedValue([
      item("1", "one"),
      item("2", "two"),
      item("3", "three"),
      item("4", "four"),
    ]);
    const view = await render(<Probe hasMessages={false} />);
    expect(api.listSuggestions).not.toHaveBeenCalled();
    await view.rerender(<Probe hasMessages />);
    await waitFor(() => expect(latest?.suggestions.map((row) => row.id)).toEqual(["1", "2", "3"]));
  });

  it("holds the fetch while a turn is busy, then loads when the refresh key changes", async () => {
    (api.listSuggestions as jest.Mock).mockResolvedValue([item("1", "one")]);
    const view = await render(<Probe hasMessages turnBusy />);
    expect(api.listSuggestions).not.toHaveBeenCalled();
    await view.rerender(<Probe hasMessages turnBusy={false} refreshKey={1} />);
    await waitFor(() => expect(api.listSuggestions).toHaveBeenCalledTimes(1));
  });

  it("drops a dismissed chip and asks the server to dismiss it", async () => {
    (api.listSuggestions as jest.Mock).mockResolvedValue([item("1", "one"), item("2", "two")]);
    (api.dismissSuggestion as jest.Mock).mockResolvedValue(undefined);
    const view = await render(<Probe hasMessages={false} />);
    await view.rerender(<Probe hasMessages />);
    await waitFor(() => expect(latest?.suggestions).toHaveLength(2));
    await act(async () => {
      await latest?.dismiss("1");
    });
    expect(latest?.suggestions.map((row) => row.id)).toEqual(["2"]);
    expect(api.dismissSuggestion).toHaveBeenCalledWith("token", "1");
  });
});
