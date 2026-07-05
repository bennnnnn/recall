import { Share } from "react-native";

import {
  EncodingType,
  writeAsStringAsync,
} from "expo-file-system/legacy";

jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "/cache/",
  EncodingType: { UTF8: "utf8" },
  writeAsStringAsync: jest.fn(),
}));

jest.mock("react-native", () => ({
  Share: { share: jest.fn() },
}));

import { formatExportJsonForShare, shareAccountExport } from "@/lib/exportData";

describe("formatExportJsonForShare", () => {
  it("pretty-prints small valid JSON", () => {
    const raw = '{"user":{"email":"a@b.com"},"chats":[],"memories":[]}';
    expect(formatExportJsonForShare(raw)).toBe(
      JSON.stringify(JSON.parse(raw), null, 2),
    );
  });

  it("returns large payloads unchanged", () => {
    const raw = `{"data":"${"x".repeat(600_000)}"}`;
    expect(formatExportJsonForShare(raw)).toBe(raw);
  });

  it("returns invalid JSON unchanged", () => {
    const raw = "{not json";
    expect(formatExportJsonForShare(raw)).toBe(raw);
  });
});

describe("shareAccountExport", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("writes to cache and shares the file url", async () => {
    await shareAccountExport('{"ok":true}');

    expect(writeAsStringAsync).toHaveBeenCalledWith(
      expect.stringMatching(/^\/cache\/recall-export-\d+\.json$/),
      '{"ok":true}',
      { encoding: EncodingType.UTF8 },
    );
    expect(Share.share).toHaveBeenCalledWith({
      url: expect.stringMatching(/^\/cache\/recall-export-\d+\.json$/),
      title: "recall-export.json",
    });
  });
});
