/**
 * The Mermaid card's chrome: a title that names the kind of diagram, a
 * full-screen view that draws a wide diagram at its own size, labels drawn
 * without emoji, and no online-editor button (the user, 2026-11-18).
 */
import { fireEvent, render } from "@testing-library/react-native";

import { MermaidBlock } from "@/components/rich/MermaidBlock";
import { previewPageFile, readyPreviewPageFile } from "@/lib/preview/previewPageFile";

jest.mock("expo-file-system/legacy", () => ({}));
jest.mock("@/lib/preview/previewPageFile", () => ({
  previewPageFile: jest.fn(),
  readyPreviewPageFile: jest.fn(() => null),
  forgetPreviewPageFile: jest.fn(),
}));

/** Each preview WebView drawn, by its testID. */
const mockWebViews = new Map<string, Record<string, unknown>>();
jest.mock("@/lib/webView", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const { View } = jest.requireActual<typeof import("react-native")>("react-native");
  function MockWebView(props: Record<string, unknown>) {
    const testID = (props.testID as string | undefined) ?? "preview-webview";
    mockWebViews.set(testID, props);
    return React.createElement(View, { testID });
  }
  return {
    ...jest.requireActual("@/lib/webView"),
    getPreviewWebView: () => ({ mode: "rnc", Component: MockWebView }),
  };
});

const ER = "erDiagram\n  BOOKS ||--o{ LOANS : has\n  MEMBERS ||--o{ LOANS : makes";

beforeEach(() => {
  mockWebViews.clear();
  jest.mocked(readyPreviewPageFile).mockReturnValue(null);
  jest.mocked(previewPageFile).mockResolvedValue("file:///cache/preview-pages/mermaid-0123.html");
});

describe("MermaidBlock card", () => {
  it("names the kind of diagram, not the tool", async () => {
    const { getByText, queryByText } = await render(<MermaidBlock content={ER} />);
    expect(getByText("rich.mermaid_kind_er")).toBeOnTheScreen();
    expect(queryByText(/Mermaid Diagram/)).toBeNull();
  });

  it("opens the diagram full screen at its own size, and closes it", async () => {
    const { findByTestId, getByLabelText, queryByTestId } = await render(<MermaidBlock content={ER} />);
    await findByTestId("preview-webview");
    expect(mockWebViews.get("preview-webview")?.injectedJavaScript).toContain('"natural":false');

    await fireEvent.press(getByLabelText("rich.diagram_full_screen"));
    await findByTestId("mermaid-full-screen-diagram");
    const full = mockWebViews.get("mermaid-full-screen-diagram");
    expect(full?.injectedJavaScript).toContain('"natural":true');
    expect(full?.scrollEnabled).toBe(true);
    expect(full?.domStorageEnabled).toBe(false);

    await fireEvent.press(getByLabelText("common.close"));
    expect(queryByTestId("mermaid-full-screen-diagram")).toBeNull();
  });

  it("draws the labels without emoji, offers no online editor, and copies the diagram as written", async () => {
    const press = 'flowchart LR\n  A["🖐️ Small piston<br/>area A₁"] --> C["📦 Large piston<br/>area A₂ > A₁"]';
    const { getByLabelText, queryByText } = await render(<MermaidBlock content={press} />);
    const drawn = String(mockWebViews.get("preview-webview")?.injectedJavaScript ?? "");
    expect(drawn).toContain("Small piston");
    expect(drawn).toContain("A₂ ﹥ A₁");
    expect(drawn).not.toMatch(/🖐|📦/u);
    expect(queryByText("rich.mermaid_editor")).toBeNull();
    expect(getByLabelText("common.copy")).toBeTruthy();
  });
});
