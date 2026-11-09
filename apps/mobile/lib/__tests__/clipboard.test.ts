import * as Clipboard from "expo-clipboard";

import { clipboardIsImageOnly, copyToClipboard } from "@/lib/clipboard";

jest.mock("expo-clipboard", () => ({
  getStringAsync: jest.fn(),
  hasImageAsync: jest.fn(),
  setStringAsync: jest.fn(),
}));

describe("copyToClipboard", () => {
  it("writes the text, and passes on a refusal", async () => {
    (Clipboard.setStringAsync as jest.Mock).mockResolvedValueOnce(true);
    await expect(copyToClipboard("x = 2")).resolves.toBeUndefined();
    expect(Clipboard.setStringAsync).toHaveBeenCalledWith("x = 2");
    (Clipboard.setStringAsync as jest.Mock).mockRejectedValueOnce(new Error("denied"));
    await expect(copyToClipboard("x")).rejects.toThrow("denied");
  });
});

describe("clipboardIsImageOnly", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("checks hasImageAsync before reading text", async () => {
    (Clipboard.hasImageAsync as jest.Mock).mockResolvedValue(false);
    await expect(clipboardIsImageOnly()).resolves.toBe(false);
    expect(Clipboard.hasImageAsync).toHaveBeenCalled();
    expect(Clipboard.getStringAsync).not.toHaveBeenCalled();
  });

  it("reads text only when an image is present", async () => {
    (Clipboard.hasImageAsync as jest.Mock).mockResolvedValue(true);
    (Clipboard.getStringAsync as jest.Mock).mockResolvedValue("");
    await expect(clipboardIsImageOnly()).resolves.toBe(true);
    expect(Clipboard.getStringAsync).toHaveBeenCalled();
  });

  it("is false when the pasteboard has both image and text", async () => {
    (Clipboard.hasImageAsync as jest.Mock).mockResolvedValue(true);
    (Clipboard.getStringAsync as jest.Mock).mockResolvedValue("notes");
    await expect(clipboardIsImageOnly()).resolves.toBe(false);
  });
});
