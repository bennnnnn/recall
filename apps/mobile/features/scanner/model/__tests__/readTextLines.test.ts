import { deleteAsync } from "expo-file-system/legacy";
import { processImageTextRecognition } from "react-native-vision-camera-mlkit";

import { textReaderLinked } from "@/features/scanner/model/nativeCamera";
import { readTextLines } from "@/features/scanner/model/readTextLines";
import { shrinkScanImage } from "@/features/scanner/model/scanImage";

jest.mock("expo-file-system/legacy", () => ({ deleteAsync: jest.fn(async () => undefined) }));
jest.mock("@/features/scanner/model/nativeCamera", () => ({ textReaderLinked: jest.fn(async () => true) }));
jest.mock("@/features/scanner/model/scanImage", () => ({ shrinkScanImage: jest.fn() }));
jest.mock("react-native-vision-camera-mlkit", () => ({ processImageTextRecognition: jest.fn() }));

const bounds = (left: number, top: number, width: number, height: number) => ({
  left, top, width, height, x: left, y: top, right: left + width, bottom: top + height,
  centerX: left + width / 2, centerY: top + height / 2,
});

function readsLines(...lines: { text: string; bounds: ReturnType<typeof bounds> }[]) {
  jest.mocked(processImageTextRecognition).mockResolvedValue({
    text: lines.map((line) => line.text).join("\n"),
    blocks: [{ text: "", bounds: bounds(0, 0, 0, 0), corners: [], languages: [], lines: lines.map((line) => ({
      ...line, corners: [], confidence: null, angle: null, languages: [], elements: [],
    })) }],
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(textReaderLinked).mockResolvedValue(true);
});

it("reads a small still as it is, as ratios of it", async () => {
  readsLines({ text: "2x + 3 = 7", bounds: bounds(100, 50, 400, 40) }, { text: " ", bounds: bounds(0, 0, 9, 9) });
  const lines = await readTextLines("file:///cut.jpg", { width: 1000, height: 500 });
  expect(processImageTextRecognition).toHaveBeenCalledWith("file:///cut.jpg");
  expect(shrinkScanImage).not.toHaveBeenCalled();
  expect(lines).toEqual([{ x: 0.1, y: 0.1, width: 0.4, height: 0.08 }]);
});

it("reads a large still through a smaller copy ML Kit accepts, and deletes the copy", async () => {
  jest.mocked(shrinkScanImage).mockResolvedValue({ uri: "file:///read-copy.jpg", width: 1600, height: 1200 });
  readsLines({ text: "F = ma", bounds: bounds(160, 120, 800, 60) });
  const lines = await readTextLines("file:///photo.jpg", { width: 4000, height: 3000 });
  expect(shrinkScanImage).toHaveBeenCalledWith("file:///photo.jpg", 1600);
  expect(processImageTextRecognition).toHaveBeenCalledWith("file:///read-copy.jpg");
  expect(lines).toEqual([{ x: 0.1, y: 0.1, width: 0.5, height: 0.05 }]);
  expect(deleteAsync).toHaveBeenCalledWith("file:///read-copy.jpg", { idempotent: true });
});

it("reads nothing where this build has no ML Kit", async () => {
  jest.mocked(textReaderLinked).mockResolvedValue(false);
  expect(await readTextLines("file:///cut.jpg", { width: 1000, height: 500 })).toEqual([]);
  expect(processImageTextRecognition).not.toHaveBeenCalled();
});

it("says so and reads nothing when ML Kit fails, still deleting the copy", async () => {
  const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
  jest.mocked(shrinkScanImage).mockResolvedValue({ uri: "file:///read-copy.jpg", width: 1600, height: 1200 });
  jest.mocked(processImageTextRecognition).mockRejectedValue(new Error("Static image exceeds the 4 MP"));
  expect(await readTextLines("file:///photo.jpg", { width: 4000, height: 3000 })).toEqual([]);
  expect(warn).toHaveBeenCalledWith("[scanner] could not read the still's text", "Static image exceeds the 4 MP");
  expect(deleteAsync).toHaveBeenCalledWith("file:///read-copy.jpg", { idempotent: true });
  warn.mockRestore();
});
