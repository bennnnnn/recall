import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useGalleryLibrary } from "@/hooks/useGalleryLibrary";
import type { AttachmentListItem } from "@/lib/api";
import { pendingFromLibraryItem } from "@/lib/pendingFromLibraryItem";
import { queueComposerAttachment } from "@/lib/pendingComposerAttachment";

let mockSession = 0;
const mockBack = jest.fn();
const mockReplace = jest.fn();
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => mockSession }));
jest.mock("@/contexts/AuthContext", () => ({ useAuthToken: () => "token" }));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
jest.mock("expo-router", () => {
  const { useEffect } = jest.requireActual<typeof import("react")>("react");
  return {
    useRouter: () => ({ canGoBack: () => true, back: mockBack, replace: mockReplace }),
    useLocalSearchParams: () => ({ composerThread: "origin" }),
    useFocusEffect: (callback: () => void) => useEffect(callback, [callback]),
  };
});
jest.mock("@/lib/api", () => ({ api: { deleteAttachment: jest.fn() } }));
jest.mock("@/lib/pendingFromLibraryItem", () => ({ pendingFromLibraryItem: jest.fn() }));
jest.mock("@/lib/pendingComposerAttachment", () => ({ queueComposerAttachment: jest.fn() }));
jest.mock("@/lib/galleryLayout", () => ({ getGalleryLayout: async () => "grid", peekGalleryLayout: () => "grid", setGalleryLayout: jest.fn() }));
jest.mock("@/lib/chatMessageCache", () => ({ clearCachedChatMessages: jest.fn() }));
jest.mock("@/lib/downloadChatAttachment", () => ({ shareChatAttachment: jest.fn() }));
jest.mock("@/lib/attachmentUri", () => ({ resolveAttachmentUri: () => "file://attachment" }));
jest.mock("@/lib/haptics", () => ({ selection: jest.fn(), tap: jest.fn() }));
const item = { id: "one", content_type: "image/png" } as AttachmentListItem;
const pending = { localUri: "file://image.png", fileName: "image.png", kind: "image", contentType: "image/png" };
let current: ReturnType<typeof useGalleryLibrary>;
function Probe() {
  const result = useGalleryLibrary([item], jest.fn());
  React.useLayoutEffect(() => { current = result; }, [result]);
  return <Text>Library</Text>;
}
beforeEach(() => { jest.clearAllMocks(); mockSession = 0; });

it("does not navigate or queue a Library attachment after leaving", async () => {
  let finish!: (value: unknown) => void;
  (pendingFromLibraryItem as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = await render(<Probe />);
  let selecting!: Promise<void>;
  await act(async () => { selecting = current.attachToComposer(item); });
  await view.unmount();
  await act(async () => { finish(pending); await selecting; });
  expect(queueComposerAttachment).not.toHaveBeenCalled();
  expect(mockBack).not.toHaveBeenCalled();
  expect(mockReplace).not.toHaveBeenCalled();
});

it("does not deliver a previous account's pending Library attachment", async () => {
  let finish!: (value: unknown) => void;
  (pendingFromLibraryItem as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const view = await render(<Probe />);
  let selecting!: Promise<void>;
  await act(async () => { selecting = current.attachToComposer(item); });
  mockSession++;
  await view.rerender(<Probe />);
  await act(async () => { finish(pending); await selecting; });
  expect(queueComposerAttachment).not.toHaveBeenCalled();
  expect(mockBack).not.toHaveBeenCalled();
});

it("delivers a successful Library pick to its originating composer", async () => {
  (pendingFromLibraryItem as jest.Mock).mockResolvedValueOnce(pending);
  await render(<Probe />);
  await act(async () => { await current.attachToComposer(item); });
  expect(queueComposerAttachment).toHaveBeenCalledWith(pending, "origin");
  expect(mockBack).toHaveBeenCalledTimes(1);
});

it("opens a PDF for reading instead of the action sheet", async () => {
  const pdf = { id: "doc", content_type: "application/pdf" } as AttachmentListItem;
  function FileProbe() {
    const result = useGalleryLibrary([pdf], jest.fn());
    React.useLayoutEffect(() => { current = result; }, [result]);
    return <Text>Library</Text>;
  }
  await render(<FileProbe />);
  await act(async () => { current.openFile(pdf); });
  expect(current.fileItem?.id).toBe("doc");
  expect(current.actionItem).toBeNull();
});

it("shares a spreadsheet on tap because it cannot be previewed in-app", async () => {
  const { shareChatAttachment } = jest.requireMock("@/lib/downloadChatAttachment") as {
    shareChatAttachment: jest.Mock;
  };
  const sheet = {
    id: "xlsx",
    content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    download_url: "/attachments/xlsx/file",
  } as AttachmentListItem;
  function FileProbe() {
    const result = useGalleryLibrary([sheet], jest.fn());
    React.useLayoutEffect(() => { current = result; }, [result]);
    return <Text>Library</Text>;
  }
  await render(<FileProbe />);
  await act(async () => { await current.openFile(sheet); });
  expect(shareChatAttachment).toHaveBeenCalled();
  expect(current.fileItem).toBeNull();
});
