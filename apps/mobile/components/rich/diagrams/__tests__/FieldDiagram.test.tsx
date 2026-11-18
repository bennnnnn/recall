/**
 * The electric field diagram's render: it draws what the fence names (every
 * line, an arrowhead per arrow, each charge or plate, the neutral point), its
 * title carries the part's letter, the canvas is one image with the fence's
 * alt, and a malformed fence shows the fallback line. Markers are hidden from
 * screen readers, so every marker query passes `HIDDEN`.
 */
import { render } from "@testing-library/react-native";

import { PhysicsDiagram } from "@/components/rich/diagrams/PhysicsDiagram";

import fixture from "../../../../../../docs/fixtures/field_scenes.json";

const HIDDEN = { includeHiddenElements: true };
const OPEN = "```simulation\n";
const body = (fence: string) => fence.slice(OPEN.length, fence.lastIndexOf("\n```"));

function scene(question: string): { raw: string; spec: Record<string, any> } {
  const found = fixture.scenes.find((item) => item.question === question);
  if (!found) throw new Error(`no scene for ${question}`);
  const raw = body(found.fence);
  return { raw, spec: JSON.parse(raw) };
}

describe("FieldDiagram", () => {
  it("draws every line, its arrow and both charges of a dipole", async () => {
    const { raw, spec } = scene("a positive and a negative charge");
    const { getByTestId, getAllByTestId, queryByTestId, getByText } = await render(
      <PhysicsDiagram content={raw} kind="field" />,
    );
    expect(getByTestId("field-canvas")).toBeTruthy();
    expect(getAllByTestId("field-line", HIDDEN)).toHaveLength(spec.field.lines.length);
    expect(getAllByTestId("field-arrow", HIDDEN)).toHaveLength(spec.field.arrows.length);
    expect(getByTestId("field-charge-positive", HIDDEN)).toBeTruthy();
    expect(getByTestId("field-charge-negative", HIDDEN)).toBeTruthy();
    expect(queryByTestId("field-neutral", HIDDEN)).toBeNull();
    // The part's letter before the title (no translation loads in tests: the English one).
    expect(getByText("(a) Electric Field")).toBeTruthy();
  });

  it("marks the neutral point between two like charges", async () => {
    const { raw } = scene("two negative charges");
    const { getAllByTestId, getByTestId } = await render(<PhysicsDiagram content={raw} kind="field" />);
    expect(getAllByTestId("field-charge-negative", HIDDEN)).toHaveLength(2);
    expect(getByTestId("field-neutral", HIDDEN)).toBeTruthy();
  });

  it("draws both plates and gives the canvas the fence's alt as one image", async () => {
    const { raw, spec } = scene("between two oppositely charged flat metal plates");
    const { getByTestId, getByLabelText } = await render(<PhysicsDiagram content={raw} kind="field" />);
    expect(getByTestId("field-plate-positive", HIDDEN)).toBeTruthy();
    expect(getByTestId("field-plate-negative", HIDDEN)).toBeTruthy();
    expect(getByLabelText(spec.alt).props.accessibilityRole).toBe("image");
  });

  it("shows the fallback line for a fence it cannot read", async () => {
    const { spec } = scene("a positive charge");
    const broken = JSON.stringify({ ...spec, field: { ...spec.field, lines: [] } });
    const { getByTestId } = await render(<PhysicsDiagram content={broken} kind="field" />);
    expect(getByTestId("physics-diagram-fallback")).toBeTruthy();
  });
});
