import { Platform } from "react-native";
import { renderHook } from "@testing-library/react-native";
import { matchFont, useFont } from "@shopify/react-native-skia";

import { useFigureFont } from "@/components/rich/skia/figureFont";
import { Type } from "@/lib/type";

/** A face that draws: "0" has a glyph. */
const SYSTEM = { name: "system", getGlyphIDs: () => [19] };
/** What a family the font manager lacks gives: a face with no glyph at all. */
const EMPTY = { name: "empty", getGlyphIDs: () => [0] };
const mockBundled = { name: "bundled" };

jest.mock("@shopify/react-native-skia", () => ({
  matchFont: jest.fn(),
  useFont: jest.fn((source: unknown) => (source ? mockBundled : null)),
}));

const os = Platform.OS;
afterEach(() => {
  Platform.OS = os;
  jest.mocked(matchFont).mockReset();
});

// A graph's axis numbers and a scene's labels were set in SpaceMono, a typewriter face the
// rest of the app never uses, loaded from a file after the figure drew.
describe("useFigureFont", () => {
  it("is the app's own face, from the system, at the figure's label size", async () => {
    jest.mocked(matchFont).mockReturnValue(SYSTEM as never);
    const { result } = await renderHook(() => useFigureFont(11));
    expect(result.current).toBe(SYSTEM);
    expect(matchFont).toHaveBeenCalledWith(
      expect.objectContaining({ fontFamily: Type.meta.fontFamily, fontStyle: "normal", fontSize: 11 }),
    );
    expect(jest.mocked(matchFont).mock.calls[0]?.[0]?.fontWeight).toBe(Type.meta.fontWeight);
    // Nothing loads beside it.
    expect(useFont).toHaveBeenLastCalledWith(null, 11);
  });

  // Android's font manager knows Roboto as "sans-serif"; "System" names nothing there.
  it("asks Android's font manager for its sans-serif", async () => {
    Platform.OS = "android";
    jest.mocked(matchFont).mockReturnValue(SYSTEM as never);
    await renderHook(() => useFigureFont(11));
    expect(matchFont).toHaveBeenCalledWith(expect.objectContaining({ fontFamily: "sans-serif" }));
  });

  // A face matched by a name the manager lacks draws nothing: the chart's numbers vanished.
  it("takes the bundled sans when the system's face draws no digits", async () => {
    jest.mocked(matchFont).mockReturnValue(EMPTY as never);
    const { result } = await renderHook(() => useFigureFont(11));
    expect(result.current).toBe(mockBundled);
    expect(jest.mocked(useFont).mock.lastCall?.[0]).toBeTruthy();
  });
});
