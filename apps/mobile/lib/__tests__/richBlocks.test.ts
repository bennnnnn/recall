import {
  detectJsonRichFenceKind,
  parseEmailDraft,
  parseQuoteAttribution,
} from "@/lib/richBlocks";

describe("detectJsonRichFenceKind", () => {
  it("BUG FIX regression: recognizes a mistagged ```json geometry fence", () => {
    // The model is instructed to use ```geometry (never ```json) for
    // diagrams, but routinely ignores that. Without this detection the
    // fence fell through to a plain syntax-highlighted JSON code block
    // instead of the triangle/rectangle/square diagram it describes.
    const json = JSON.stringify({
      type: "right_triangle",
      base: 4,
      height: 5,
      unit: "cm",
      show_labels: true,
      show_hypotenuse: true,
      show_angle: true,
    });
    expect(detectJsonRichFenceKind(json)).toBe("geometry");
  });

  it("recognizes a mistagged ```json circle fence", () => {
    const json = JSON.stringify({ type: "circle", radius: 4, unit: "cm" });
    expect(detectJsonRichFenceKind(json)).toBe("geometry");
  });

  it("recognizes a mistagged ```json graph fence", () => {
    const json = JSON.stringify({
      type: "function",
      expr: "x**2",
      points: [
        [-2, 4],
        [0, 0],
        [2, 4],
      ],
    });
    expect(detectJsonRichFenceKind(json)).toBe("graph");
  });

  it("returns null for ordinary json that is not a geometry/graph spec", () => {
    expect(detectJsonRichFenceKind(JSON.stringify({ foo: "bar" }))).toBeNull();
  });

  it("returns null for non-JSON content", () => {
    expect(detectJsonRichFenceKind("not json at all")).toBeNull();
  });
});

describe("parseQuoteAttribution", () => {
  it("splits a trailing dash line as the author", () => {
    expect(parseQuoteAttribution("To be or not to be.\n— Shakespeare")).toEqual({
      quote: "To be or not to be.",
      author: "Shakespeare",
    });
  });

  it("needs a newline or a spaced dash — glued em dash stays in the quote", () => {
    expect(parseQuoteAttribution("To be or not to be.— Shakespeare")).toEqual({
      quote: "To be or not to be.— Shakespeare",
    });
  });

  it("splits a trailing spaced em dash on the same line", () => {
    expect(
      parseQuoteAttribution(
        "Courage is the most important of all the virtues. — Maya Angelou",
      ),
    ).toEqual({
      quote: "Courage is the most important of all the virtues.",
      author: "Maya Angelou",
    });
  });
});

describe("parseEmailDraft", () => {
  it("BUG FIX regression: drops bracketed To/name slots so the card is send-ready", () => {
    const draft = parseEmailDraft(
      [
        "To: [Manager's Email Address]",
        "Subject: Request for Time Off - [Your Name] - This Friday",
        "",
        "Hi [Manager's Name],",
        "",
        "I would like to request Friday off.",
        "",
        "Best regards,",
        "Bini",
      ].join("\n"),
    );
    expect(draft).toEqual({
      subject: "Request for Time Off - This Friday",
      body: "Hi,\n\nI would like to request Friday off.\n\nBest regards,\nBini",
    });
    expect(draft?.to).toBeUndefined();
    expect(draft?.body).not.toContain("[");
  });

  it("keeps a real To address and markdown links in the body", () => {
    const draft = parseEmailDraft(
      [
        "To: jane@work.com",
        "Subject: Friday off",
        "",
        "Hi Jane,",
        "",
        "See [the policy](https://example.com/pto).",
      ].join("\n"),
    );
    expect(draft).toEqual({
      to: "jane@work.com",
      subject: "Friday off",
      body: "Hi Jane,\n\nSee [the policy](https://example.com/pto).",
    });
  });
});
