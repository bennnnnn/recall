import { IconSize } from "@/ui/icons/sizes";
import { Layer } from "@/lib/layer";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Italic, Type, Weight } from "@/lib/type";

describe("type and space tokens", () => {
  it("owns the screen type roles on the iOS text scale", () => {
    expect(Type.body.fontSize).toBe(17);
    expect(Type.reading.fontSize).toBe(18);
    expect(Type.secondary.fontSize).toBe(15);
    expect(Type.caption.fontSize).toBe(12);
    expect(Type.compact.fontSize).toBe(13);
    expect(Type.label.fontSize).toBe(15);
    expect(Type.callout.fontSize).toBe(16);
    expect(Type.navTitle.fontSize).toBe(17);
    expect(Type.title.fontSize).toBe(20);
    expect(Type.display.fontSize).toBe(28);
    for (const role of Object.values(Type)) expect(role.fontFamily).toBe("System");
  });

  it("pairs the system face with each real weight", () => {
    expect(Weight.regular).toEqual({ fontFamily: "System", fontWeight: "400" });
    expect(Weight.medium).toEqual({ fontFamily: "System", fontWeight: "500" });
    expect(Weight.semibold).toEqual({ fontFamily: "System", fontWeight: "600" });
    expect(Weight.bold).toEqual({ fontFamily: "System", fontWeight: "700" });
    expect(Italic.bold).toEqual({ fontFamily: "System", fontWeight: "700", fontStyle: "italic" });
  });

  it("gives every text role air: about the old face's 1.42 em, chat text 1.55", () => {
    for (const role of Object.values(Type)) {
      if (!("lineHeight" in role)) continue;
      const ratio = role.lineHeight / role.fontSize;
      expect(ratio).toBeGreaterThanOrEqual(1.2);
      expect(ratio).toBeLessThanOrEqual(1.56);
    }
    expect(Type.reading.lineHeight).toBe(28);
    // The time picker's digits keep the face's own line: their box is sized from it.
    expect(Type.clock).not.toHaveProperty("lineHeight");
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
    expect(Radius.card).toBe(20);
    expect(Radius.menu).toBe(24);
    expect(Radius.sheet).toBe(28);
    expect(Radius.dialog).toBe(28);
    expect(Radius.composer).toBe(28);
    expect(IconSize.xxs).toBe(14);
    expect(IconSize.xs).toBe(16);
    expect(IconSize.sm).toBe(20);
    expect(IconSize.md).toBe(24);
    expect(IconSize.lg).toBe(28);
    expect(IconSize.xl).toBe(40);
    expect(IconSize.hero).toBe(56);
    expect(Layer.toast).toBe(9999);
    expect(Layer.drawer).toBeGreaterThan(Layer.composer);
    expect(Layer.sheet).toBeGreaterThan(Layer.composerExpanded);
    expect(Layer.composerExpanded).toBeGreaterThan(Layer.composer);
    expect(Layer.composer).toBeGreaterThan(Layer.header);
  });
});
