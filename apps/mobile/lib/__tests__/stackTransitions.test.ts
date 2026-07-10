jest.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

import {
  stackAuthTransition,
  stackHomeTransition,
  stackPushTransition,
  stackUtilityTransition,
} from "@/lib/stackTransitions";
import { Platform } from "react-native";

describe("stackTransitions", () => {
  it("stackPushTransition enables back gestures", () => {
    Platform.OS = "ios";
    const iosPreset = stackPushTransition();
    expect(iosPreset.gestureEnabled).toBe(true);
    expect(iosPreset.animation).toBe("default");

    Platform.OS = "android";
    const androidPreset = stackPushTransition();
    expect(androidPreset.animation).toBe("slide_from_right");
  });

  it("stackUtilityTransition uses fade_from_bottom", () => {
    expect(stackUtilityTransition().animation).toBe("fade_from_bottom");
  });

  it("stackAuthTransition fades without gestures", () => {
    const preset = stackAuthTransition();
    expect(preset.animation).toBe("fade");
    expect(preset.gestureEnabled).toBe(false);
  });

  it("stackHomeTransition does not animate", () => {
    expect(stackHomeTransition().animation).toBe("none");
  });
});
