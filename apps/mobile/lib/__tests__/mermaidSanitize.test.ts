import { sanitizeMermaidNodeLabels } from "@/lib/mermaidSanitize";

const GRIND = "D --> E[Grind Beans (Medium Grind)]";
const GRIND_QUOTED = 'D --> E["Grind Beans (Medium Grind)"]';

describe("sanitizeMermaidNodeLabels", () => {
  it("quotes a parenthetical rectangle label", () => {
    expect(sanitizeMermaidNodeLabels(GRIND)).toBe(GRIND_QUOTED);
  });

  it("leaves already-quoted labels unchanged", () => {
    expect(sanitizeMermaidNodeLabels(GRIND_QUOTED)).toBe(GRIND_QUOTED);
  });

  it("leaves stadium start([Start]) unchanged", () => {
    const line = "start([Start]) --> step[Do the work]";
    expect(sanitizeMermaidNodeLabels(line)).toBe(line);
  });
});
