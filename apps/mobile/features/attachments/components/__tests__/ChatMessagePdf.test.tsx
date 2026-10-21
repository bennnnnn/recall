import { render } from "@testing-library/react-native";
import { StyleSheet } from "react-native";

import { ChatMessagePdf } from "@/features/attachments/components/ChatMessagePdf";
import { lightTheme as mockLightTheme } from "@/lib/theme";

jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => "tok" }));
jest.mock("@/features/attachments/hooks/useAttachmentIndexed", () => ({
  useAttachmentIndexed: () => ({ indexed: true, failed: false }),
}));
jest.mock("@/features/attachments/hooks/usePdfPreview", () => ({
  usePdfPreview: () => ({ status: "ready", webViewKey: "doc", webViewProps: {} }),
}));
jest.mock("@/hooks/useDeferredWebViewMount", () => ({
  useDeferredWebViewMount: () => ({ canMount: true, onLoaded: jest.fn() }),
}));
jest.mock("@/features/attachments/model/attachmentUri", () => ({
  resolveAttachmentUri: ({ attachmentId }: { attachmentId?: string }) => `https://api.test/attachments/${attachmentId}/file`,
}));
jest.mock("@/features/attachments/model/downloadChatAttachment", () => ({
  downloadChatAttachment: jest.fn(),
}));
jest.mock("@/features/attachments/components/AttachmentPdfViewer", () => ({
  AttachmentPdfViewer: () => null,
}));
jest.mock("@/ui/overlay/dialogs", () => ({ alertDialog: jest.fn() }));
jest.mock("@/ui/icons/Icon", () => ({ Icon: "Icon" }));
jest.mock("@/lib/theme", () => ({
  ...jest.requireActual("@/lib/theme"),
  useTheme: () => mockLightTheme,
}));
jest.mock("@/lib/webView", () => ({
  getPreviewWebView: () => ({
    mode: "rnc",
    Component: () => {
      const { View: MockView } = jest.requireActual<typeof import("react-native")>("react-native");
      return <MockView testID="pdf-webview" />;
    },
  }),
  useStaticOnlyNavigation: () => undefined,
}));

it("gives the page preview a width of its own that nothing between shrinks", async () => {
  const { findByTestId } = await render(<ChatMessagePdf attachmentId="doc" fileName="lease-notes.pdf" />);
  // A sent message's column is aligned to the end, so the preview needs its own width; and
  // react-native-webview's container takes its width from its parent's alignItems.
  // Either one left the page 0 wide: an empty box under the card.
  let node = (await findByTestId("pdf-webview")).parent;
  let width: unknown;
  while (node && width === undefined) {
    const style = StyleSheet.flatten(node.props.style) ?? {};
    expect(style.alignItems === undefined || style.alignItems === "stretch").toBe(true);
    width = typeof style.width === "number" ? style.width : undefined;
    node = node.parent;
  }
  expect(width).toBeGreaterThan(0);
});
