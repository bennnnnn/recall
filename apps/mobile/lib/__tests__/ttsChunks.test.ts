import { splitTtsLead, TTS_LEAD_MAX_CHARS } from "@/lib/ttsChunks";

describe("splitTtsLead", () => {
  it("keeps short text as a single lead", () => {
    expect(splitTtsLead("Hello there.")).toEqual({
      lead: "Hello there.",
      rest: "",
    });
  });

  it("cuts at the last sentence in the lead window", () => {
    const first =
      "This is the opening sentence, long enough that a later paragraph should not delay the first sound.";
    const second =
      "And this is a much longer follow-up that should wait for the second request after playback has already started for the lead.";
    const padded = `${first} ${second} ${second} ${second}`;
    const { lead, rest } = splitTtsLead(padded);
    expect(lead.startsWith("This is the opening")).toBe(true);
    expect(lead.includes("And this is a much longer")).toBe(false);
    expect(rest.startsWith("And this")).toBe(true);
  });

  it("falls back to a word boundary when there is no sentence end", () => {
    const word = "alpha ";
    const text = word.repeat(80).trim();
    const { lead, rest } = splitTtsLead(text);
    expect(lead.length).toBeLessThanOrEqual(TTS_LEAD_MAX_CHARS);
    expect(lead.endsWith("alpha") || lead.endsWith("alpha.")).toBe(true);
    expect(rest.length).toBeGreaterThan(0);
  });
});
