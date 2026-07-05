import { formatExportJsonForShare } from "@/lib/exportData";

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
