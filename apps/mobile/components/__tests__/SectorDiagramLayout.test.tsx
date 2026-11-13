import { render } from "@testing-library/react-native";
import { Dimensions } from "react-native";

import { GeometryBlock } from "@/components/rich/GeometryBlock";

const mockSvgText = jest.fn((_props: Record<string, unknown>) => null);
const mockSvgPath = jest.fn((_props: Record<string, unknown>) => null);
jest.mock("react-native-svg", () => ({
  ...jest.requireActual("react-native-svg"),
  __esModule: true,
  Text: (props: Record<string, unknown>) => mockSvgText(props),
  Path: (props: Record<string, unknown>) => mockSvgPath(props),
}));

type RenderNode = { type?: string; props?: Record<string, unknown>; children?: unknown[] };
function nodesIn(value: unknown): RenderNode[] {
  if (Array.isArray(value)) return value.flatMap(nodesIn);
  if (!value || typeof value !== "object") return [];
  const node = value as RenderNode;
  return [node, ...(node.children ?? []).flatMap(nodesIn)];
}

describe("sector canvas follows its actual swept bounds", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 390, height: 844, scale: 3, fontScale: 1 });
    mockSvgText.mockClear();
    mockSvgPath.mockClear();
  });
  afterEach(() => jest.restoreAllMocks());

  it.each([90, 180, 270, 360])("preserves the %i degree arc with readable labels and nearby footers", async (angle) => {
    const { toJSON } = await render(<GeometryBlock content={JSON.stringify({
      type: "sector", radius: 4, angle_deg: angle, unit: "units",
      area: 1, arc_length: 1,
    })} />);
    const svg = nodesIn(toJSON()).find((node) => node.type === "RNSVGSvgView")!;
    const width = Number(svg.props?.width);
    const height = Number(svg.props?.height);
    const path = String(mockSvgPath.mock.calls[0][0].d);
    const numbers = path.match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/g)!.map(Number);
    const [cx, cy, x1, y1, radius] = numbers;
    expect(radius).toBe(131);
    expect(x1).toBe(cx);
    expect(y1).toBe(cy - radius);
    expect(path.match(/A/g)).toHaveLength(angle === 360 ? 2 : 1);
    const [x2, y2] = numbers.slice(-2);
    expect(x2).toBeCloseTo(cx + radius * Math.sin(angle * Math.PI / 180), 10);
    expect(y2).toBeCloseTo(cy - radius * Math.cos(angle * Math.PI / 180), 10);
    const plotBottom = cy + (angle >= 180 ? radius : 0);
    const labels = mockSvgText.mock.calls.map(([props]) => props);
    const area = labels.find((props) => String(props.children).startsWith("Area"))!;
    const arc = labels.find((props) => String(props.children).startsWith("Arc length"))!;
    expect(area.y).toBe(plotBottom + 34);
    expect(arc.y).toBe(plotBottom + 50);
    expect(area.x).toBe(width / 2);
    expect(arc.x).toBe(width / 2);
    expect(height - Number(arc.y)).toBe(12);
    if (angle === 90) expect(height).toBeLessThan(240);
    expect(width).toBeLessThanOrEqual(390 - 28);
    for (const label of labels) {
      expect(label.fontSize).toBe(12);
      const inkWidth = Math.ceil(Array.from(String(label.children)).length * 12 * 0.65);
      const left = Number(label.x) - (label.textAnchor === "end" ? inkWidth : inkWidth / 2);
      expect(left).toBeGreaterThanOrEqual(0);
      expect(left + inkWidth).toBeLessThanOrEqual(width);
      expect(Number(label.y)).toBeGreaterThan(12);
      expect(Number(label.y)).toBeLessThan(height);
    }
  });

  it("draws a quarter circle as a quarter, labelled with the quarter's own area", async () => {
    // The server's figure for "the area of the quarter circle of radius 8 cm (use 3.14)":
    // the whole circle (201.06 cm²) was drawn once.
    await render(<GeometryBlock content={JSON.stringify({
      type: "sector", radius: 8, angle_deg: 90, unit: "cm", show_labels: true, area: 50.24,
      labels: { radius: "8 cm", area: "50.24 cm²", angle: "90°" },
    })} />);
    const path = String(mockSvgPath.mock.calls[0][0].d);
    const numbers = path.match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/g)!.map(Number);
    const [cx, cy, x1, y1, radius] = numbers;
    const [x2, y2] = numbers.slice(-2);
    // From 12 o'clock to 3 o'clock, one short arc, closed by both radii.
    expect([x1, y1]).toEqual([cx, cy - radius]);
    expect(x2).toBeCloseTo(cx + radius, 10);
    expect(y2).toBeCloseTo(cy, 10);
    expect(path).toMatch(/ 0 0 1 /);
    expect(path.endsWith("Z")).toBe(true);
    const texts = mockSvgText.mock.calls.map(([props]) => String(props.children));
    expect(texts).toContain("Area:\u00A050.24 cm²");
    expect(texts).toContain("90°");
    expect(texts.filter((text) => text === "8 cm")).toHaveLength(2);
    expect(texts.some((text) => text.startsWith("Arc length") || text.includes("201"))).toBe(false);
  });

  it("labels a part's perimeter under the figure and leaves out what the server did not send", async () => {
    const { toJSON } = await render(<GeometryBlock content={JSON.stringify({
      type: "sector", radius: 5, angle_deg: 180, unit: "cm", perimeter: 25.71, area: null,
      labels: { radius: "5 cm", perimeter: "25.71 cm", angle: "180°" },
    })} />);
    const texts = mockSvgText.mock.calls.map(([props]) => String(props.children));
    expect(texts).toContain("Perimeter:\u00A025.71 cm");
    // A null measure is absent, never drawn as 0.00.
    expect(texts.some((text) => text.startsWith("Area") || text.includes("0.00"))).toBe(false);
    const svg = nodesIn(toJSON()).find((node) => node.type === "RNSVGSvgView")!;
    const footer = mockSvgText.mock.calls.map(([props]) => props)
      .find((props) => String(props.children).startsWith("Perimeter"))!;
    expect(Number(svg.props?.height) - Number(footer.y)).toBe(28);
  });

  it("stacks three measures under the figure without clipping the last", async () => {
    const { toJSON } = await render(<GeometryBlock content={JSON.stringify({
      type: "sector", radius: 4, angle_deg: 90, unit: "cm", area: 12.57, arc_length: 6.28,
      perimeter: 14.28,
    })} />);
    const svg = nodesIn(toJSON()).find((node) => node.type === "RNSVGSvgView")!;
    const footers = mockSvgText.mock.calls.map(([props]) => props)
      .filter((props) => /^(Area|Arc length|Perimeter):/.test(String(props.children)));
    expect(footers.map((props) => String(props.children).split(":")[0]))
      .toEqual(["Area", "Arc length", "Perimeter"]);
    const ys = footers.map((props) => Number(props.y));
    expect(ys[1] - ys[0]).toBe(16);
    expect(ys[2] - ys[1]).toBe(16);
    expect(Number(svg.props?.height) - ys[2]).toBe(12);
  });

  it("does not reserve footer space when labels are hidden", async () => {
    const { toJSON } = await render(<GeometryBlock content={JSON.stringify({
      type: "sector", radius: 4, angle_deg: 90, show_labels: false,
    })} />);
    const svg = nodesIn(toJSON()).find((node) => node.type === "RNSVGSvgView")!;
    expect(svg.props?.height).toBe(183);
    expect(mockSvgText).not.toHaveBeenCalled();
  });
});
