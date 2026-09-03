import { preprocessMarkdown } from "@/lib/markdown/markdownPreprocess";
import {
  flattenIntegrationConnectNotes,
  isIntegrationConnectNote,
} from "@/lib/markdown/flattenIntegrationConnectNotes";

describe("flattenIntegrationConnectNotes", () => {
  it("unwraps a quote-card blockquote for Calendar and Gmail connect copy", () => {
    const src =
      "> Google Calendar and Gmail are not connected — you can link them in Settings → Google Calendar and Settings → Gmail if you'd like to see events or emails.";
    const out = flattenIntegrationConnectNotes(src);
    expect(out.startsWith(">")).toBe(false);
    expect(out).toContain("Google Calendar and Gmail are not connected");
    expect(isIntegrationConnectNote(src)).toBe(true);
  });

  it("unwraps > Note: connect copy so it does not become a callout card", () => {
    const src =
      "> Note: Gmail is not connected. Connect it in Settings → Gmail for inbox items.";
    const out = flattenIntegrationConnectNotes(src);
    expect(out).not.toMatch(/^>/);
    expect(out.toLowerCase().startsWith("note:")).toBe(false);
    expect(out).toContain("Gmail is not connected");
  });

  it("leaves a real attributed quote blockquote alone", () => {
    const src =
      "> Courage is the most important of all the virtues because without courage, you can't practice any other virtue consistently.\n>\n> — Maya Angelou";
    expect(flattenIntegrationConnectNotes(src)).toBe(src);
  });
});

describe("preprocessMarkdown connect notes", () => {
  it("does not leave a Calendar/Gmail connect sentence as a blockquote or callout fence", () => {
    const src =
      "> Google Calendar and Gmail are not connected — you can link them in Settings → Google Calendar and Settings → Gmail if you'd like to see events or emails.";
    const out = preprocessMarkdown(src);
    expect(out.trim().startsWith(">")).toBe(false);
    expect(out).not.toContain("```callout");
    expect(out).toContain("Google Calendar and Gmail are not connected");
  });
});
