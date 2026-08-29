const platform = { OS: "ios" };

jest.mock("react-native", () => ({
  Platform: platform,
  Share: {
    share: jest.fn(),
    sharedAction: "sharedAction",
    dismissedAction: "dismissedAction",
  },
}));

jest.mock("expo-print", () => ({
  printToFileAsync: jest.fn(),
}));

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: { t: (key: string) => key },
}));

import { Platform, Share } from "react-native";

import { presentShareSheet, shareConversation } from "@/lib/share";
import type { Message } from "@/lib/api";

describe("share sheet", () => {
  beforeEach(() => {
    platform.OS = "ios";
    jest.mocked(Share.share).mockReset();
    jest.mocked(Share.share).mockResolvedValue({ action: Share.sharedAction });
  });

  it("opens the native share sheet with message and iOS subject", async () => {
    await presentShareSheet({ message: "Hello thread", title: "My chat" });
    expect(Share.share).toHaveBeenCalledWith(
      { message: "Hello thread", title: "My chat" },
      { subject: "My chat" },
    );
  });

  it("uses dialogTitle on Android", async () => {
    Platform.OS = "android";
    await presentShareSheet({ message: "Hello thread", title: "My chat" });
    expect(Share.share).toHaveBeenCalledWith(
      { message: "Hello thread", title: "My chat" },
      { dialogTitle: "My chat" },
    );
  });

  it("does not throw when the user dismisses the sheet", async () => {
    jest.mocked(Share.share).mockRejectedValueOnce(new Error("User did not share"));
    await expect(
      presentShareSheet({ message: "Hello thread", title: "My chat" }),
    ).resolves.toBeUndefined();
  });

  it("rejects an empty payload instead of opening a blank sheet", async () => {
    await expect(presentShareSheet({ message: "   " })).rejects.toThrow("share_empty");
    expect(Share.share).not.toHaveBeenCalled();
  });

  it("shares a markdown transcript so the OS app list can open", async () => {
    const messages = [
      { id: "u1", role: "user", content: "hello" },
      { id: "a1", role: "assistant", content: "hi there" },
    ] as Message[];
    await shareConversation("Factorials", messages);
    expect(Share.share).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Factorials",
        message: expect.stringContaining("**share.role_user:**\nhello"),
      }),
      { subject: "Factorials" },
    );
    const payload = jest.mocked(Share.share).mock.calls[0]?.[0] as { message: string };
    expect(payload.message).toContain("**share.role_assistant:**\nhi there");
    expect(payload.message).toContain("# Factorials");
  });
});
