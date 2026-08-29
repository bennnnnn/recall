import { IconSize } from "@/lib/icons";
import { Layer } from "@/lib/layer";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";

describe("type and space tokens", () => {
  it("owns the screen type roles", () => {
    expect(Type.body.fontSize).toBe(16);
    expect(Type.secondary.fontSize).toBe(14);
    expect(Type.caption.fontSize).toBe(12);
    expect(Type.body.lineHeight).toBe(25);
    expect(Type.label.fontSize).toBe(14);
    expect(Type.title.fontSize).toBe(20);
    expect(Type.display.fontSize).toBe(28);
  });

  it("uses a 4pt spacing scale", () => {
    expect(Space.xxs).toBe(4);
    expect(Space.xs).toBe(8);
    expect(Space.sm).toBe(12);
    expect(Space.md).toBe(16);
    expect(Space.gutter).toBe(20);
    expect(Space.lg).toBe(24);
    expect(Space.xl).toBe(32);
    expect(Space.minTouch).toBe(44);
  });

  it("owns chrome radius, icon, and overlay layers", () => {
    expect(Radius.md).toBe(12);
    expect(Radius.sheet).toBe(20);
    expect(IconSize.sm).toBe(20);
    expect(IconSize.md).toBe(22);
    expect(IconSize.lg).toBe(24);
    expect(Layer.toast).toBe(9999);
    expect(Layer.drawer).toBeGreaterThan(Layer.composer);
    expect(Layer.composer).toBeGreaterThan(Layer.header);
  });
});
