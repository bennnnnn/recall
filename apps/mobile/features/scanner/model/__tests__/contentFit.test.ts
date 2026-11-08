import { boxIn, fitToContent, shotCrop, type ImageBox } from "@/features/scanner/model/contentFit";

const SIZE = { width: 1000, height: 1000 };
const line = (x: number, y: number, width: number, height = 0.04): ImageBox => ({ x, y, width, height });

describe("fitToContent on a camera shot (an aim)", () => {
  const aim: ImageBox = { x: 0.2, y: 0.4, width: 0.5, height: 0.2 };

  it("widens the frame over a line it cut, padded, and never shrinks it", () => {
    // "2x + 3 = 7" runs past the frame's right edge.
    const fit = fitToContent([line(0.3, 0.48, 0.55)], SIZE, aim)!;
    expect(fit.x).toBeCloseTo(0.2, 5);
    expect(fit.y).toBeCloseTo(0.4, 5);
    expect(fit.x + fit.width).toBeCloseTo(0.85 + 0.02, 5);
    expect(fit.y + fit.height).toBeCloseTo(0.6, 5);
  });

  it("stays put when the text is well inside the frame", () => {
    expect(fitToContent([line(0.3, 0.48, 0.2)], SIZE, aim)).toBeNull();
  });

  it("leaves out the next problem, whose middle is below the frame", () => {
    expect(fitToContent([line(0.3, 0.48, 0.2), line(0.1, 0.59, 0.9)], SIZE, aim)).toBeNull();
  });

  it("keeps a diagram it cannot read: the frame never gets smaller than the aim", () => {
    const fit = fitToContent([line(0.25, 0.42, 0.1, 0.02)], SIZE, aim);
    expect(fit === null || (fit.width >= aim.width && fit.height >= aim.height)).toBe(true);
  });
});

describe("fitToContent on a photo (no aim)", () => {
  it("takes every line, dropping the margins and the desk", () => {
    const fit = fitToContent([line(0.3, 0.3, 0.3), line(0.3, 0.36, 0.25)], SIZE, null)!;
    expect(fit.x).toBeCloseTo(0.3 - 0.02, 5);
    expect(fit.y).toBeCloseTo(0.3 - 0.02, 5);
    expect(fit.x + fit.width).toBeCloseTo(0.6 + 0.02, 5);
    expect(fit.y + fit.height).toBeCloseTo(0.4 + 0.02, 5);
  });

  it("pads by half a line when lines are tall", () => {
    const fit = fitToContent([line(0.3, 0.3, 0.3, 0.1)], SIZE, null)!;
    expect(fit.y).toBeCloseTo(0.25, 5);
  });

  it("ignores specks, and moves nothing for a photo with no text", () => {
    expect(fitToContent([line(0.5, 0.5, 0.01, 0.002)], SIZE, null)).toBeNull();
    expect(fitToContent([], SIZE, null)).toBeNull();
  });

  it("moves nothing when the text already fills the photo", () => {
    expect(fitToContent([line(0.01, 0.01, 0.98, 0.97)], SIZE, null)).toBeNull();
  });

  it("pads in pixels, so a wide photo gets the same margin on every side", () => {
    const fit = fitToContent([line(0.4, 0.4, 0.2, 0.1)], { width: 2000, height: 1000 }, null)!;
    expect((0.4 - fit.x) * 2000).toBeCloseTo((0.4 - fit.y) * 1000, 5);
  });
});

describe("shotCrop", () => {
  it("keeps room around the live frame, and says where the frame is in the cut", () => {
    const frame = { originX: 1000, originY: 1000, width: 1000, height: 500 };
    const { crop, aim } = shotCrop(frame, { width: 3000, height: 4000 });
    expect(crop).toEqual({ originX: 800, originY: 900, width: 1400, height: 700 });
    expect(aim.x).toBeCloseTo(200 / 1400, 10);
    expect(aim.width).toBeCloseTo(1000 / 1400, 10);
    expect(aim.y).toBeCloseTo(100 / 700, 10);
  });

  it("stops the room at the photo's edges", () => {
    const { crop, aim } = shotCrop({ originX: 0, originY: 0, width: 500, height: 500 }, { width: 600, height: 550 });
    expect(crop).toEqual({ originX: 0, originY: 0, width: 600, height: 550 });
    expect(aim).toEqual(boxIn({ originX: 0, originY: 0, width: 500, height: 500 }, { width: 600, height: 550 }));
  });
});
