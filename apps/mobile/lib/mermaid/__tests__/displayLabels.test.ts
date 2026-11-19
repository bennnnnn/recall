import { mermaidDisplaySource } from "@/lib/mermaid/displayLabels";

describe("mermaid labels as the card draws them", () => {
  it("drops the emoji the model decorated the hydraulic press with, and writes > so it draws", () => {
    const press = [
      "flowchart LR",
      '    A["🖐️ Small piston<br/>force F₁, area A₁"] -->|"push down"| B["Oil-filled chamber<br/>(incompressible liquid)"]',
      '    B -->|"pressure spreads equally"| C["🔼 Large piston<br/>area A₂ > A₁"]',
      '    C -->|"lift"| D["📦 Load F₂"]',
    ].join("\n");
    expect(mermaidDisplaySource(press)).toBe(
      [
        "flowchart LR",
        '    A["Small piston<br/>force F₁, area A₁"] -->|"push down"| B["Oil-filled chamber<br/>(incompressible liquid)"]',
        '    B -->|"pressure spreads equally"| C["Large piston<br/>area A₂ ﹥ A₁"]',
        '    C -->|"lift"| D["Load F₂"]',
      ].join("\n"),
    );
  });

  it("leaves arrows, line breaks and plain symbols alone", () => {
    const sequence = 'sequenceDiagram\n    A->>B: "x < y"\n    C<|--D\n    E["Brand™ © 2026<br/>a ≥ b"] --> F';
    expect(mermaidDisplaySource(sequence)).toBe(
      'sequenceDiagram\n    A->>B: "x ﹤ y"\n    C<|--D\n    E["Brand™ © 2026<br/>a ≥ b"] --> F',
    );
  });

  it("drops emoji built from joiners, skin tones and keycaps", () => {
    expect(mermaidDisplaySource('A["👩‍🔬 Scientist"] --> B["👍🏽 ok"] --> C["1️⃣ First"]')).toBe(
      'A["Scientist"] --> B["ok"] --> C["First"]',
    );
  });

  it("returns a diagram with nothing to clean as it was", () => {
    const plain = "flowchart TD\n    A[Start] --> B{Is it?}\n    B -->|Yes| C[Done]";
    expect(mermaidDisplaySource(plain)).toBe(plain);
  });
});
