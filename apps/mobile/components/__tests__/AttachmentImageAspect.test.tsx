import { act, fireEvent, render } from "@testing-library/react-native";
import { type ImageProps, StyleSheet } from "react-native";

import { ChatMessageImage } from "@/components/ChatMessageImage";
import { ComposerAttachmentPreview } from "@/components/ComposerAttachmentPreview";
import { fitAttachmentImage } from "@/lib/attachmentImageSize";
import { resolveAttachmentUri } from "@/lib/attachmentUri";
import type { PendingAttachment } from "@/lib/attachments";

jest.mock("@/components/Icon", () => ({ Icon: "Icon" }));
jest.mock("@/components/AttachmentImageViewer", () => {
  const { View: MockView } = jest.requireActual("react-native");
  return { AttachmentImageViewer: ({ visible }: { visible: boolean }) => visible ? <MockView testID="image-viewer" /> : null };
});
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => "test-token" }));
jest.mock("@/lib/attachmentUri", () => ({
  resolveAttachmentUri: jest.fn(({ localUri, path, attachmentId }: { localUri?: string; path?: string; attachmentId?: string }) => localUri || path || (attachmentId ? `https://api.test/attachments/${attachmentId}/file` : null)),
  attachmentRequestHeaders: (uri: string) => uri.startsWith("https://api.test/") ? { Authorization: "Bearer test-token" } : {},
}));
jest.mock("@/lib/downloadChatAttachment", () => ({ ensureLocalAttachmentFile: jest.fn().mockResolvedValue("file:///cached.jpg") }));
jest.mock("@/lib/motion", () => ({ motionMs: (value: number) => value, useReduceMotion: () => false }));
jest.mock("react-native-reanimated", () => {
  const { Image: MockImage } = jest.requireActual("react-native");
  return {
    __esModule: true,
    default: { createAnimatedComponent: () => (props: ImageProps) => <MockImage testID="animated-image" {...props} /> },
    Easing: { out: (value: unknown) => value, ease: "ease" },
    useAnimatedStyle: (fn: () => unknown) => fn(),
    useSharedValue: (value: number) => ({ value }),
    withTiming: (value: number) => value,
  };
});

const load = (width: number, height: number) => ({ nativeEvent: { source: { width, height, uri: "decoded" } } });
const photo = (localUri: string): PendingAttachment => ({ kind: "image", localUri, fileName: "scan.jpg", contentType: "image/jpeg" });

describe("decoded attachment frame proportions", () => {
  it.each([
    [1200, 300, 148, 37],
    [300, 1200, 47.25, 189],
    [800, 800, 148, 148],
  ])("fits %s by %s inside both chat limits", async (width, height, expectedWidth, expectedHeight) => {
    const view = await render(<ChatMessageImage localUri="file:///scan.jpg" previewFit="contain" width={148} height={189} />);
    await fireEvent(view.getByTestId("chat-image-preview"), "load", load(width, height));
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: expectedWidth, height: expectedHeight });
    expect(view.getByTestId("chat-image-preview").props.resizeMode).toBe("contain");
  });

  it("uses authenticated remote onLoad dimensions without changing the image source", async () => {
    const view = await render(<ChatMessageImage attachmentId="a" animatedReveal={false} previewFit="contain" width={148} height={189} />);
    expect(resolveAttachmentUri).toHaveBeenLastCalledWith({ attachmentId: "a", localUri: undefined, path: undefined });
    expect(view.getByTestId("chat-image-preview").props.source).toEqual({ uri: "https://api.test/attachments/a/file", headers: { Authorization: "Bearer test-token" } });
    await fireEvent(view.getByTestId("chat-image-preview"), "load", load(1600, 900));
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: 148, height: 83.25 });
  });

  it("resets when a local image is replaced and ignores the old image's late events", async () => {
    const view = await render(<ChatMessageImage localUri="file:///old.jpg" previewFit="contain" width={148} height={189} />);
    const staleLoad = view.getByTestId("chat-image-preview").props.onLoad;
    const staleError = view.getByTestId("chat-image-preview").props.onError;
    await fireEvent(view.getByTestId("chat-image-preview"), "load", load(1200, 300));
    await view.rerender(<ChatMessageImage attachmentId="new" animatedReveal={false} previewFit="contain" width={148} height={189} />);
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: 148, height: 189 });
    await act(() => { staleLoad(load(300, 1200)); staleError(); });
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: 148, height: 189 });
    expect(view.getByTestId("chat-image-preview")).toBeOnTheScreen();
    await fireEvent(view.getByTestId("chat-image-preview"), "load", load(900, 900));
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: 148, height: 148 });
  });

  it.each([[0, 1], [-1, 1], [1, 0], [NaN, 10], [Infinity, 10]])("declines invalid decoded size %s by %s", async (width, height) => {
    const view = await render(<ChatMessageImage localUri="file:///scan.jpg" previewFit="contain" width={148} height={189} />);
    await fireEvent(view.getByTestId("chat-image-preview"), "load", load(width, height));
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: 148, height: 189 });
    expect(fitAttachmentImage({ width, height }, { width: 148, height: 189 })).toBeNull();
  });

  it("retains a usable failed-image frame and opens the existing viewer", async () => {
    const view = await render(<ChatMessageImage localUri="file:///scan.jpg" previewFit="contain" width={148} height={189} />);
    await fireEvent(view.getByTestId("chat-image-preview"), "error");
    expect(view.queryByTestId("chat-image-preview")).toBeNull();
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: 148, height: 189 });
    await fireEvent.press(view.getByRole("button"));
    expect(view.getByTestId("image-viewer")).toBeOnTheScreen();
  });

  it("leaves generated image dimensions and cover behavior unchanged after load", async () => {
    const view = await render(<ChatMessageImage path="https://images.test/generated.jpg" width={148} height={189} />);
    const layers = view.getAllByTestId("animated-image");
    expect(layers).toHaveLength(2);
    expect(layers.every((layer) => layer.props.resizeMode === "cover")).toBe(true);
    await fireEvent(layers[1], "load", load(1200, 300));
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: 148, height: 189 });
  });

  it("re-fits a loaded image if its available bounds change", async () => {
    const view = await render(<ChatMessageImage localUri="file:///scan.jpg" previewFit="contain" width={148} height={189} />);
    await fireEvent(view.getByTestId("chat-image-preview"), "load", load(1200, 300));
    await view.rerender(<ChatMessageImage localUri="file:///scan.jpg" previewFit="contain" width={100} height={120} />);
    expect(view.getByTestId("chat-image-frame")).toHaveStyle({ width: 100, height: 25 });
  });

  it.each([[1200, 300, 88, 22], [300, 1200, 28, 112]])("fits composer %s by %s without clipping the remove action", async (width, height, expectedWidth, expectedHeight) => {
    const onRemove = jest.fn();
    const view = await render(<ComposerAttachmentPreview attachment={photo("file:///scan.jpg")} onRemove={onRemove} />);
    await fireEvent(view.getByTestId("composer-image-preview"), "load", load(width, height));
    expect(view.getByTestId("composer-image-frame")).toHaveStyle({ width: expectedWidth, height: expectedHeight, overflow: "hidden" });
    const host = StyleSheet.flatten(view.getByTestId("composer-image-controls").props.style);
    expect(host.width).toBeGreaterThanOrEqual(44);
    expect(host.height).toBeGreaterThanOrEqual(44);
    expect(host.backgroundColor).toBeUndefined();
    expect(host.overflow).toBeUndefined();
    await fireEvent.press(view.getByRole("button"));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("resets composer sizing on URI change and keeps upload removal disabled", async () => {
    const onRemove = jest.fn();
    const view = await render(<ComposerAttachmentPreview attachment={photo("file:///old.jpg")} onRemove={onRemove} />);
    const staleLoad = view.getByTestId("composer-image-preview").props.onLoad;
    await fireEvent(view.getByTestId("composer-image-preview"), "load", load(1200, 300));
    await view.rerender(<ComposerAttachmentPreview attachment={photo("file:///new.jpg")} onRemove={onRemove} uploading />);
    await act(() => staleLoad(load(300, 1200)));
    expect(view.getByTestId("composer-image-frame")).toHaveStyle({ width: 88, height: 112 });
    expect(view.getByTestId("composer-image-controls").props.accessibilityState.busy).toBe(true);
    await fireEvent.press(view.getByRole("button"));
    expect(onRemove).not.toHaveBeenCalled();
    await fireEvent(view.getByTestId("composer-image-preview"), "load", load(1200, 300));
    expect(view.getByTestId("composer-image-frame")).toHaveStyle({ width: 88, height: 22 });
  });
});
