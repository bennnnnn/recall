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

  it("leaves arrows, names, plain symbols and a one-line comparison alone", () => {
    const sequence = 'sequenceDiagram\n    A->>B: "x < y"\n    C<|--D\n    E["Brand™ © 2026<br/>a ≥ b"] --> F["Is x < 5?"]';
    expect(mermaidDisplaySource(sequence)).toBe(sequence);
  });

  it("keeps a label that is only emoji, and anything outside a label", () => {
    const only = 'flowchart LR\n    A["✅"] -->|"✅"| B{"❓"}\n    C((🔥)) --> D[✅]';
    expect(mermaidDisplaySource(only)).toBe(only);
    const sequence = "sequenceDiagram\n    participant 👤\n    👤->>B: hi 🙂";
    expect(mermaidDisplaySource(sequence)).toBe(sequence);
  });

  it("reads a label over several lines as one, so the arrow after it is untouched", () => {
    const twoLines = 'flowchart LR\n    A["Step one\ncontinues 🔼"] --> B["Next<br/>a > b"]';
    expect(mermaidDisplaySource(twoLines)).toBe('flowchart LR\n    A["Step one\ncontinues"] --> B["Next<br/>a ﹥ b"]');
    const inch = 'sequenceDiagram\n    A->>B: a 12" pipe\n    B-->>A: ok';
    expect(mermaidDisplaySource(inch)).toBe(inch);
  });

  it("cleans a label of every shape: flag, parallelogram, trapezoid", () => {
    const shapes = 'flowchart LR\n    A>"📦 Flag<br/>a > b"] --> B[/"📦 Input<br/>x < y"/]\n    B --> C[\\"⚙️ Step"\\] --> D[/"🔼 Up"\\]';
    expect(mermaidDisplaySource(shapes)).toBe(
      'flowchart LR\n    A>"Flag<br/>a ﹥ b"] --> B[/"Input<br/>x ﹤ y"/]\n    B --> C[\\"Step"\\] --> D[/"Up"\\]',
    );
  });

  it("cleans an unquoted label of a node or an edge, and leaves the names and arrows around it", () => {
    const bare =
      "flowchart LR\n    A[📦 Load] -->|📦 loaded| B(🔥 Hot) --> C{❓ Ok?}\n    C -->|yes| D[[⚙️ Sub]] --> E((🚀 Go)) --> F>📦 Flag]\n    F --> G[/📦 In/] --> H[Step<br/>a > b 📦]";
    expect(mermaidDisplaySource(bare)).toBe(
      "flowchart LR\n    A[Load] -->|loaded| B(Hot) --> C{Ok?}\n    C -->|yes| D[[Sub]] --> E((Go)) --> F>Flag]\n    F --> G[/In/] --> H[Step<br/>a ﹥ b]",
    );
    const syntax = "erDiagram\n    BOOKS ||--o{ LOANS : has\nclassDiagram\n    Animal <|-- Duck\nstateDiagram-v2\n    [*] --> On";
    expect(mermaidDisplaySource(syntax)).toBe(syntax);
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
