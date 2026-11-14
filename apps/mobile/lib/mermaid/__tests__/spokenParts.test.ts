import { mermaidSpokenParts } from "@/lib/mermaid/kind";

describe("mermaidSpokenParts (GFX-02: what a screen reader hears of a diagram)", () => {
  it("reads a flowchart's node texts in order, once each", () => {
    const source = "flowchart TD\n  A[Start] --> B{Is it raining?}\n  B -->|yes| C(Take an umbrella)\n  B --> A";
    expect(mermaidSpokenParts(source)).toBe("Start, Is it raining?, Take an umbrella");
  });

  it("reads a sequence diagram's participants by their shown names", () => {
    const source = "sequenceDiagram\n  participant U as User\n  actor S as Server\n  U->>S: Hello";
    expect(mermaidSpokenParts(source)).toBe("User, Server");
  });

  it("reads quoted labels and a title, never the declaration or comments", () => {
    const source = '%% a comment\npie\n  title Pets\n  "Dogs" : 386\n  "Cats" : 85';
    expect(mermaidSpokenParts(source)).toBe("Pets, Dogs, Cats");
  });

  it("strips a nested shape's inner brackets", () => {
    expect(mermaidSpokenParts("graph LR\n  db[(Database)] --> app([App])")).toBe("Database, App");
  });

  it("is empty when the source names nothing", () => {
    expect(mermaidSpokenParts("graph TD\n  A --> B")).toBe("");
  });

  it("stops at twelve parts", () => {
    const nodes = Array.from({ length: 20 }, (_, i) => `  N${i}[Step ${i}]`).join("\n");
    expect(mermaidSpokenParts(`graph TD\n${nodes}`).split(", ")).toHaveLength(12);
  });
});
