import React from "react";
import { Text } from "react-native";
import { render, screen, waitFor } from "@testing-library/react-native";

import { useDraftChat } from "@/hooks/useDraftChat";
import { api } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: {
    createChat: jest.fn(),
    deleteChat: jest.fn(async () => undefined),
    deleteChatIfEmpty: jest.fn(async () => undefined),
  },
}));
jest.mock("@/lib/cache/chatListCache", () => ({
  rememberCreatedChat: jest.fn(),
}));

function Probe({ chatId = null }: { chatId?: string | null }) {
  const draft = useDraftChat({ token: "token", chatId });
  return <Text testID="draft-id">{draft.draftChatId ?? "none"}</Text>;
}

describe("useDraftChat latency prewarm", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (api.createChat as jest.Mock).mockResolvedValue({ id: "draft-1" });
  });

  it("creates a fresh draft before the first Send tap", async () => {
    render(<Probe />);

    expect(api.createChat).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(api.createChat).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("draft-id").props.children).toBe("draft-1");
    });
    expect(api.createChat).toHaveBeenCalledWith("token", "auto", undefined, undefined);
  });

  it("does not create a competing draft while an existing chat is opening", () => {
    render(<Probe chatId="existing-1" />);

    expect(api.createChat).not.toHaveBeenCalled();
  });
});
