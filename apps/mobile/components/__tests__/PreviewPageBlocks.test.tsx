/**
 * Mermaid diagrams, charts and SMILES drawings load one shared page file per
 * kind (lib/previewPageFile.ts) and hand it each block's data, instead of
 * building a page of up to 3.4 MB per block. These tests pin what the WebView
 * gets: the file, the data, and settings no looser than the inline pages had.
 */
import { act, render, waitFor } from "@testing-library/react-native";
import type { ReactElement } from "react";

import { ChartBlock } from "@/components/rich/ChartBlock";
import { Chemistry2DView } from "@/components/rich/ChemistryBlock";
import { MermaidBlock } from "@/components/rich/MermaidBlock";
import { CHART_PAGE } from "@/lib/chartPreviewHtml";
import { SMILES_DRAWER_PAGE } from "@/lib/chemistry/smilesDrawerHtml";
import { MERMAID_PAGE } from "@/lib/mermaidPreviewHtml";
import type { PreviewPage } from "@/lib/previewPage";
import {
  forgetPreviewPageFile,
  previewPageFile,
  readyPreviewPageFile,
} from "@/lib/previewPageFile";

jest.mock("expo-file-system/legacy", () => ({}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/previewPageFile", () => ({
  previewPageFile: jest.fn(),
  readyPreviewPageFile: jest.fn(() => null),
  forgetPreviewPageFile: jest.fn(),
}));

const mockTheme = { dark: false };
jest.mock("@/lib/theme", () => {
  const actual = jest.requireActual("@/lib/theme");
  return { ...actual, useTheme: () => (mockTheme.dark ? actual.darkTheme : actual.lightTheme) };
});

/** Every render of the preview WebView, and how many times one mounted. */
const mockWebView = { renders: [] as Record<string, unknown>[], mounts: 0 };
jest.mock("@/lib/webView", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const { View } = jest.requireActual<typeof import("react-native")>("react-native");
  function MockWebView(props: Record<string, unknown>) {
    React.useEffect(() => {
      mockWebView.mounts += 1;
    }, []);
    mockWebView.renders.push(props);
    return React.createElement(View, { testID: "preview-webview" });
  }
  return {
    ...jest.requireActual("@/lib/webView"),
    getPreviewWebView: () => ({ mode: "rnc", Component: MockWebView }),
  };
});

const lastProps = () => mockWebView.renders[mockWebView.renders.length - 1]!;

type Case = {
  page: PreviewPage;
  element: (data: string) => ReactElement;
  /** The block's data, and another to switch to. */
  data: [string, string];
  /** How the data reads inside the injected JSON. */
  inScript: (data: string) => string;
  failure: string;
};

const CASES: [string, Case][] = [
  [
    "a Mermaid diagram",
    {
      page: MERMAID_PAGE,
      element: (data) => <MermaidBlock content={data} />,
      data: ["graph TD; A-->B", "graph LR; X-->Y"],
      inScript: (data) => `"source":${JSON.stringify(data)}`,
      failure: "rich.mermaid_error",
    },
  ],
  [
    "a chart",
    {
      page: CHART_PAGE,
      element: (data) => <ChartBlock content={data} />,
      data: ['{"mark":"bar"}', '{"mark":"line"}'],
      inScript: (data) => JSON.stringify(data),
      failure: "rich.chart_error",
    },
  ],
  [
    "a SMILES drawing",
    {
      page: SMILES_DRAWER_PAGE,
      element: (data) => <Chemistry2DView smiles={data} />,
      data: ["CCO", "c1ccccc1"],
      inScript: (data) => `"smiles":${JSON.stringify(data)}`,
      failure: "rich.chemistry_renderer_unavailable",
    },
  ],
];

const fileFor = (page: PreviewPage) => `file:///cache/preview-pages/${page.name}-0123456789abcdef.html`;

beforeEach(() => {
  mockWebView.renders.length = 0;
  mockWebView.mounts = 0;
  mockTheme.dark = false;
  jest.mocked(readyPreviewPageFile).mockReset().mockReturnValue(null);
  jest.mocked(forgetPreviewPageFile).mockReset();
  jest.mocked(previewPageFile).mockReset().mockImplementation(async (page) => fileFor(page));
});

describe.each(CASES)("%s", (_name, { page, element, data, inScript, failure }) => {
  const file = fileFor(page);

  it("loads its kind's page file and hands it this block's data", async () => {
    const { findByTestId } = await render(element(data[0]));
    await findByTestId("preview-webview");

    expect(previewPageFile).toHaveBeenCalledWith(page);
    const props = lastProps();
    expect(props.source).toEqual({ uri: file });
    // Handed before the page loads and again once it has (Android may run the first late).
    expect(props.injectedJavaScriptBeforeContentLoaded).toBe(props.injectedJavaScript);
    expect(props.injectedJavaScript).toContain(inScript(data[0]));
  });

  it("keeps the WebView as locked down as the inline page was", async () => {
    const { findByTestId } = await render(element(data[0]));
    await findByTestId("preview-webview");
    const props = lastProps();

    expect(props.javaScriptEnabled).toBe(true);
    expect(props.domStorageEnabled).toBe(false);
    // Android needs file access to open a file:// page; iOS reads only the page itself.
    expect(props.allowFileAccess).toBe(true);
    expect(props.allowingReadAccessToURL).toBeUndefined();
    expect(props.allowFileAccessFromFileURLs).toBeUndefined();
    expect(props.allowUniversalAccessFromFileURLs).toBeUndefined();
    expect(props.originWhitelist).toEqual(["*"]);

    const allow = props.onShouldStartLoadWithRequest as (request: { url: string }) => boolean;
    expect(allow({ url: file })).toBe(true);
    expect(allow({ url: "https://example.com/?leak=1" })).toBe(false);
    expect(allow({ url: "file:///cache/att-1-2-doc.pdf" })).toBe(false);
  });

  it("waits for the page file before mounting a WebView", async () => {
    let finish: (uri: string) => void = () => undefined;
    jest.mocked(previewPageFile).mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const { queryByTestId, findByTestId } = await render(element(data[0]));
    expect(queryByTestId("preview-webview")).toBeNull();

    await act(async () => finish(file));
    expect(await findByTestId("preview-webview")).toBeTruthy();
  });

  it("mounts at once on a page file this run already has", async () => {
    jest.mocked(readyPreviewPageFile).mockReturnValue(file);
    const { findByTestId } = await render(element(data[0]));
    await findByTestId("preview-webview");
    expect(previewPageFile).not.toHaveBeenCalled();
    expect(lastProps().source).toEqual({ uri: file });
  });

  it("says so when the page file cannot be written", async () => {
    jest.mocked(previewPageFile).mockRejectedValue(new Error("Storage unavailable."));
    const { findByText, queryByTestId } = await render(element(data[0]));
    expect(await findByText(failure)).toBeTruthy();
    expect(queryByTestId("preview-webview")).toBeNull();
  });

  it("forgets a page file the WebView could not load", async () => {
    const { findByTestId, findByText } = await render(element(data[0]));
    await findByTestId("preview-webview");
    await act(async () => (lastProps().onError as () => void)());

    expect(forgetPreviewPageFile).toHaveBeenCalledWith(page);
    expect(await findByText(failure)).toBeTruthy();
  });

  it("starts a fresh WebView on the same file for new data or a new theme", async () => {
    const view = await render(element(data[0]));
    await view.findByTestId("preview-webview");
    expect(mockWebView.mounts).toBe(1);

    await view.rerender(element(data[1]));
    await waitFor(() => expect(mockWebView.mounts).toBe(2));
    expect(lastProps().injectedJavaScript).toContain(inScript(data[1]));

    mockTheme.dark = true;
    await view.rerender(element(data[1]));
    await waitFor(() => expect(mockWebView.mounts).toBe(3));
    expect(lastProps().source).toEqual({ uri: file });
    expect(previewPageFile).toHaveBeenCalledTimes(1);
  });
});
