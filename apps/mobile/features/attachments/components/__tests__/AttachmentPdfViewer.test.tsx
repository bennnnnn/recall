import { act, render, waitFor } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { AttachmentPdfViewer } from "@/features/attachments/components/AttachmentPdfViewer";
import { ensureLocalAttachmentFile } from "@/features/attachments/model/downloadChatAttachment";
import { PDF_VIEWER_PAGE } from "@/lib/pdfPreviewHtml";
import { previewPageFile } from "@/lib/previewPageFile";
import { lightTheme as mockLightTheme } from "@/lib/theme";
import { readVendorLibraries } from "@/lib/vendorAssets";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => "tok" }));
jest.mock("@/features/attachments/model/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId?: string }) => `https://api.test/attachments/${attachmentId}/file`,
}));
jest.mock("@/features/attachments/model/downloadChatAttachment", () => ({
  ensureLocalAttachmentFile: jest.fn(),
}));
jest.mock("@/lib/previewPageFile", () => ({
  previewPageFile: jest.fn(async () => "file:///cache/preview-pages/pdf-viewer-0123456789abcdef.html"),
}));
jest.mock("@/lib/vendorAssets", () => ({
  readVendorLibraries: jest.fn(async () => ({ pdf: "/*pdf.js*/", pdfWorker: "/*worker*/" })),
}));
jest.mock("expo-file-system/legacy", () => ({
  cacheDirectory: "file:///cache/",
  EncodingType: { Base64: "base64" },
  readAsStringAsync: jest.fn(async () => "QUJD"),
}));
jest.mock("@/lib/pdfPreviewHtml", () => ({
  ...jest.requireActual("@/lib/pdfPreviewHtml"),
  buildPdfPreviewHtml: (base64: string) => `<html>${base64}</html>`,
}));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));

const mockWebViewProps: Record<string, unknown>[] = [];
jest.mock("@/lib/webView", () => ({
  ...jest.requireActual("@/lib/webView"),
  getPreviewWebView: () => ({
    mode: "rnc",
    Component: (props: Record<string, unknown>) => {
      mockWebViewProps.push(props);
      const { View: MockView } = jest.requireActual<typeof import("react-native")>("react-native");
      return <MockView testID="pdf-webview" />;
    },
  }),
}));

const lastProps = () => mockWebViewProps[mockWebViewProps.length - 1]!;

function viewer(visible: boolean) {
  return (
    <AttachmentPdfViewer visible={visible} onClose={jest.fn()} onShare={jest.fn()} attachmentId="doc" fileName="doc.pdf" />
  );
}

beforeEach(() => {
  mockWebViewProps.length = 0;
  jest.mocked(ensureLocalAttachmentFile).mockReset().mockResolvedValue("file:///cache/att-1-2-doc.pdf");
});

it("loads the shared pdf.js page from disk and lets it read the cached PDF, every page", async () => {
  const { findByTestId } = await render(viewer(true));
  await findByTestId("pdf-webview");
  expect(ensureLocalAttachmentFile).toHaveBeenCalledWith(expect.objectContaining({
    uri: "https://api.test/attachments/doc/file", fileName: "doc.pdf", signal: expect.any(AbortSignal),
  }));
  const props = lastProps();
  expect(previewPageFile).toHaveBeenCalledWith(PDF_VIEWER_PAGE);
  expect(props.source).toEqual({ uri: "file:///cache/preview-pages/pdf-viewer-0123456789abcdef.html" });
  expect(props.allowingReadAccessToURL).toBe("file:///cache/");
  expect(props.allowFileAccessFromFileURLs).toBe(true);
  expect(props.injectedJavaScriptBeforeContentLoaded).toContain('"src":"file:///cache/att-1-2-doc.pdf"');
  expect(props.injectedJavaScriptBeforeContentLoaded).toContain('"allPages":true');
});

it("falls back to the inline page when the WebView cannot read the file", async () => {
  const { findByTestId } = await render(viewer(true));
  await findByTestId("pdf-webview");
  const onMessage = lastProps().onMessage as (event: { nativeEvent: { data: string } }) => void;
  await act(async () => {
    onMessage({ nativeEvent: { data: JSON.stringify({ type: "pdf-error" }) } });
  });
  await waitFor(() => expect(lastProps().source).toEqual({ html: "<html>QUJD</html>" }));
  // pdf.js rides in the inline page too, read from its vendored asset.
  expect(readVendorLibraries).toHaveBeenCalledWith(["pdf", "pdfWorker"]);
  // The bytes come from the cached file, not a second download.
  expect(ensureLocalAttachmentFile).toHaveBeenLastCalledWith(expect.objectContaining({ uri: "https://api.test/attachments/doc/file" }));
});

it("stops the download when the viewer closes", async () => {
  jest.mocked(ensureLocalAttachmentFile).mockReturnValueOnce(new Promise(() => {}));
  const view = await render(viewer(true));
  const signal = jest.mocked(ensureLocalAttachmentFile).mock.calls[0]![0].signal!;
  expect(signal.aborted).toBe(false);
  await view.rerender(viewer(false));
  expect(signal.aborted).toBe(true);
});

it("lays the pages out across the screen: nothing above the page shrinks it", async () => {
  const { findByTestId } = await render(viewer(true));
  // react-native-webview's container takes its width from its parent's alignItems;
  // centered, it shrank to its content and the page drew 0 wide.
  let node = (await findByTestId("pdf-webview")).parent;
  while (node) {
    const align = StyleSheet.flatten(node.props.style)?.alignItems;
    expect(align === undefined || align === "stretch").toBe(true);
    node = node.parent;
  }
});
