import { renderHook } from "@testing-library/react-native";
import { matchFont } from "@shopify/react-native-skia";

import { useFigureFont } from "@/components/rich/skia/figureFont";
import { Type } from "@/lib/type";

jest.mock("@shopify/react-native-skia", () => ({ matchFont: jest.fn(() => ({ name: "system" })) }));

// A graph's axis numbers and a scene's labels were set in SpaceMono, a typewriter face the
// rest of the app never uses, loaded from a file after the figure drew.
describe("useFigureFont", () => {
  it("is the app's own face, from the system, at the figure's label size", async () => {
    const { result } = await renderHook(() => useFigureFont(11));
    expect(result.current).toEqual({ name: "system" });
    expect(matchFont).toHaveBeenCalledWith(
      expect.objectContaining({ fontFamily: Type.meta.fontFamily, fontStyle: "normal", fontSize: 11 }),
    );
    expect(jest.mocked(matchFont).mock.calls[0]?.[0]?.fontWeight).toBe(Type.meta.fontWeight);
  });
});
