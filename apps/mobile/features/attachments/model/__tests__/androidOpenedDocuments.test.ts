import { watchAndroidOpenedDocuments } from "@/features/attachments/model/androidOpenedDocuments";
import { receiveOpenedDocument } from "@/features/attachments/model/openedDocument";

const SHARED = "content://com.whatsapp.provider.media/item/9";

const mockRemove = jest.fn();
let mockArrival: (() => void) | null = null;
const mockNative = {
  takeDocumentAsync: jest.fn(),
  markLaunchHandledAsync: jest.fn(async () => undefined),
  addListener: jest.fn((_event: string, listener: () => void) => {
    mockArrival = listener;
    return { remove: mockRemove };
  }),
};
let mockModule: unknown = mockNative;

jest.mock("expo-modules-core", () => ({ requireOptionalNativeModule: () => mockModule }));
jest.mock("@/features/attachments/model/openedDocument", () => ({ receiveOpenedDocument: jest.fn() }));

const received = jest.mocked(receiveOpenedDocument);

function settle(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

beforeEach(() => {
  jest.clearAllMocks();
  mockModule = mockNative;
  mockArrival = null;
});

it("takes the file that launched Recall, then each one Android hands it while it runs", async () => {
  mockNative.takeDocumentAsync
    .mockResolvedValueOnce({ uri: SHARED, name: "Lease.pdf", size: 2048, type: "application/pdf" })
    .mockResolvedValueOnce({ uri: "content://downloads/document/7", name: null, size: null, type: null });
  const stop = watchAndroidOpenedDocuments();
  await settle();
  expect(mockNative.addListener).toHaveBeenCalledWith("onDocument", expect.any(Function));
  // The name, size and type the provider gave, read off the JS thread.
  expect(received).toHaveBeenCalledWith(SHARED, { name: "Lease.pdf", size: 2048, type: "application/pdf" }, undefined);

  mockArrival?.();
  await settle();
  expect(received).toHaveBeenLastCalledWith("content://downloads/document/7", {}, undefined);

  stop();
  expect(mockRemove).toHaveBeenCalled();
});

it("holds nothing when no file is waiting or the read fails", async () => {
  const warn = jest.spyOn(console, "warn").mockImplementation(() => undefined);
  mockNative.takeDocumentAsync.mockResolvedValueOnce(null).mockRejectedValueOnce(new Error("revoked"));
  watchAndroidOpenedDocuments();
  await settle();
  mockArrival?.();
  await settle();
  expect(received).not.toHaveBeenCalled();
  expect(warn).toHaveBeenCalledWith("[openedFile]", { stage: "take", error: "Error" });
  warn.mockRestore();
});

it("drops what is not a name, a size or a type", async () => {
  mockNative.takeDocumentAsync.mockResolvedValueOnce({ uri: SHARED, name: 7, size: -1, type: "" });
  watchAndroidOpenedDocuments();
  await settle();
  expect(received).toHaveBeenCalledWith(SHARED, {}, undefined);
});

it("marks the launch that brought a file handled only when Recall says it is done with it", async () => {
  mockNative.takeDocumentAsync.mockResolvedValueOnce({ uri: SHARED, launch: "7:120:content://x" });
  watchAndroidOpenedDocuments();
  await settle();
  const handled = received.mock.calls[0]?.[2];
  expect(handled).toEqual(expect.any(Function));
  expect(mockNative.markLaunchHandledAsync).not.toHaveBeenCalled();
  handled?.();
  expect(mockNative.markLaunchHandledAsync).toHaveBeenCalledWith("7:120:content://x");
});

it("watches nothing in a build without the module (iOS, Expo Go, an older build)", () => {
  mockModule = null;
  const stop = watchAndroidOpenedDocuments();
  expect(mockNative.takeDocumentAsync).not.toHaveBeenCalled();
  expect(() => stop()).not.toThrow();
});
