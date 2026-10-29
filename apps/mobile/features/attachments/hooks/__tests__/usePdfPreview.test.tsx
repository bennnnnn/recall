/**
 * The PDF card and viewer hand no navigation to the OS: every URL reaches the
 * viewer's guard (react-native-webview opens one that misses `originWhitelist`
 * with `Linking.openURL`, no tap needed), and on Android a window the page
 * opens stays in the WebView instead of a bare one that hands its URL to the
 * system. Both the file-backed page and the inline fallback.
 */
import { renderHook, waitFor } from "@testing-library/react-native";

import { usePdfPreview } from "@/features/attachments/hooks/usePdfPreview";

const mockSession = { account: "user-1", getToken: () => "token" };
jest.mock("@/contexts/accountSession", () => ({ useAccountSession: () => mockSession }));
jest.mock("@/features/attachments/model/downloadChatAttachment", () => ({
  ensureLocalAttachmentFile: async () => "file:///cache/attachments/att-1-doc.pdf",
}));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  EncodingType: { Base64: "base64" },
  readAsStringAsync: async () => "JVBERi0xLjQK",
}));
jest.mock("@/lib/previewPageFile", () => ({
  previewPageFile: async () => "file:///cache/preview-pages/pdf-viewer-0123456789abcdef.html",
  forgetPreviewPageFile: jest.fn(),
}));
jest.mock("@/lib/vendorAssets", () => ({
  readVendorLibraries: async () => ({ pdf: "", pdfWorker: "" }),
}));
jest.mock("@/lib/theme", () => {
  const actual = jest.requireActual("@/lib/theme");
  return { ...actual, useTheme: () => actual.lightTheme };
});

const mockWebView = { mode: "rnc" as "rnc" | "expo-dom" };
jest.mock("@/lib/webView", () => ({
  ...jest.requireActual("@/lib/webView"),
  getPreviewWebView: () => ({ mode: mockWebView.mode, Component: () => null }),
}));

describe.each([
  ["the page file (react-native-webview)", "rnc"],
  ["the inline page (any other WebView)", "expo-dom"],
] as const)("a PDF preview on %s", (_name, mode) => {
  it("sends every URL to its guard and opens no window of its own", async () => {
    mockWebView.mode = mode;
    const { result } = await renderHook(() =>
      usePdfPreview({ uri: "https://api.test/attachments/1", fileName: "doc.pdf", enabled: true, allPages: true }),
    );
    await waitFor(() => expect(result.current.status).toBe("ready"));
    const preview = result.current;
    if (preview.status !== "ready") throw new Error("not ready");

    const source = mode === "rnc" ? { uri: expect.stringMatching(/^file:/) } : { html: expect.any(String) };
    expect(preview.webViewProps.source).toEqual(source);
    expect(preview.webViewProps.originWhitelist).toEqual(["*"]);
    expect(preview.webViewProps.setSupportMultipleWindows).toBe(false);
  });
});
