import { act, renderHook } from "@testing-library/react-native";

import { useScanContentFit, type FitShot } from "@/features/scanner/hooks/useScanContentFit";
import type { ImageBox } from "@/features/scanner/model/contentFit";
import { readTextLines } from "@/features/scanner/model/readTextLines";

jest.mock("@/features/scanner/model/readTextLines", () => ({ readTextLines: jest.fn() }));

/** The still is drawn in the middle half of the view. */
const FRAME = { x: 0.25, y: 0.25, width: 0.5, height: 0.5 };

async function setup(preview: FitShot, lines: ImageBox[]) {
  let resolveRead: (read: ImageBox[]) => void = () => undefined;
  jest.mocked(readTextLines).mockReturnValue(new Promise((resolve) => { resolveRead = resolve; }));
  let adjusted = 0;
  const crop = { resetRegion: jest.fn(), fitRegion: jest.fn(), adjustments: () => adjusted };
  const hook = await renderHook(() => useScanContentFit({ preview, previewFrame: FRAME, crop }));
  return {
    crop,
    hook,
    adjust: () => { adjusted += 1; },
    land: async () => act(async () => resolveRead(lines)),
  };
}

const PHOTO: FitShot = { localUri: "file:///page.jpg", width: 1000, height: 1000 };
const TEXT = [{ x: 0.4, y: 0.4, width: 0.2, height: 0.04 }];

beforeEach(() => jest.clearAllMocks());

it("opens on the whole photo, then moves onto its text once read", async () => {
  const { crop, land } = await setup(PHOTO, TEXT);
  expect(crop.resetRegion).toHaveBeenCalledWith(FRAME);
  expect(readTextLines).toHaveBeenCalledWith("file:///page.jpg", PHOTO);
  await land();
  const [fit] = crop.fitRegion.mock.calls[0]!;
  // The text (0.4..0.6 of the photo, padded by 0.06) drawn in the middle half of the view.
  expect(fit.x).toBeCloseTo(0.25 + 0.34 * 0.5, 5);
  expect(fit.width).toBeCloseTo(0.32 * 0.5, 5);
});

it("opens a camera shot where the student aimed", async () => {
  const aim = { x: 0.1, y: 0.2, width: 0.8, height: 0.6 };
  const { crop } = await setup({ ...PHOTO, aim }, []);
  expect(crop.resetRegion).toHaveBeenCalledWith({ x: 0.3, y: 0.35, width: 0.4, height: 0.3 });
});

it("leaves a frame the student moved before the read landed", async () => {
  const { crop, adjust, land } = await setup(PHOTO, TEXT);
  adjust();
  await land();
  expect(crop.fitRegion).not.toHaveBeenCalled();
});

it("drops a read that lands after the still is gone", async () => {
  const { crop, hook, land } = await setup(PHOTO, TEXT);
  await hook.unmount();
  await land();
  expect(crop.fitRegion).not.toHaveBeenCalled();
});

it("leaves the frame where it opened when the still has no text", async () => {
  const { crop, land } = await setup(PHOTO, []);
  await land();
  expect(crop.fitRegion).not.toHaveBeenCalled();
});
