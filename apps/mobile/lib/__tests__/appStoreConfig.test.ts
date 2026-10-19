import appJson from "../../app.json";

/**
 * Store-review guards on app.json. Expo decides the order its config plugins write
 * Info.plist in, so every plugin that writes a usage description must carry the text
 * in ios.infoPlist, or whichever plugin happens to run last replaces it.
 */
const USAGE_DESCRIPTION_OPTIONS: Record<string, Record<string, string>> = {
  "expo-location": {
    locationWhenInUsePermission: "NSLocationWhenInUseUsageDescription",
    motionUsagePermission: "NSMotionUsageDescription",
  },
  "expo-image-picker": {
    photosPermission: "NSPhotoLibraryUsageDescription",
    cameraPermission: "NSCameraUsageDescription",
    microphonePermission: "NSMicrophoneUsageDescription",
  },
  "expo-media-library": {
    photosPermission: "NSPhotoLibraryUsageDescription",
    savePhotosPermission: "NSPhotoLibraryAddUsageDescription",
  },
  "expo-camera": {
    cameraPermission: "NSCameraUsageDescription",
    microphonePermission: "NSMicrophoneUsageDescription",
  },
  "expo-audio": {
    microphonePermission: "NSMicrophoneUsageDescription",
  },
  "@config-plugins/react-native-webrtc": {
    cameraPermission: "NSCameraUsageDescription",
    microphonePermission: "NSMicrophoneUsageDescription",
  },
};

function pluginOptions(name: string): Map<string, unknown> {
  const plugins: readonly unknown[] = appJson.expo.plugins;
  for (const entry of plugins) {
    if (Array.isArray(entry) && entry[0] === name) {
      return new Map(Object.entries(entry[1] ?? {}));
    }
  }
  throw new Error(`app.json has no options for ${name}`);
}

const infoPlist = new Map<string, unknown>(Object.entries(appJson.expo.ios.infoPlist));

describe("app store config", () => {
  it.each(Object.entries(USAGE_DESCRIPTION_OPTIONS))(
    "%s writes the same usage descriptions as ios.infoPlist",
    (plugin, options) => {
      const configured = pluginOptions(plugin);
      for (const [option, key] of Object.entries(options)) {
        expect(infoPlist.get(key)).toEqual(expect.any(String));
        expect({ [option]: configured.get(option) }).toEqual({ [option]: infoPlist.get(key) });
      }
    },
  );

  it("leaves out permissions the app never asks for", () => {
    expect(pluginOptions("expo-secure-store").get("faceIDPermission")).toBe(false);
    const location = pluginOptions("expo-location");
    expect(location.get("locationAlwaysPermission")).toBe(false);
    expect(location.get("locationAlwaysAndWhenInUsePermission")).toBe(false);
    for (const key of [
      "NSFaceIDUsageDescription",
      "NSLocationAlwaysUsageDescription",
      "NSLocationAlwaysAndWhenInUseUsageDescription",
    ]) {
      expect(infoPlist.has(key)).toBe(false);
    }
  });

  it("never plays audio in the background", () => {
    // Read-aloud stops and Live Talk hangs up when the app leaves the foreground.
    expect(pluginOptions("expo-audio").get("enableBackgroundPlayback")).toBe(false);
    expect(infoPlist.has("UIBackgroundModes")).toBe(false);
    expect(appJson.expo.android.blockedPermissions).toEqual(
      expect.arrayContaining([
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK",
      ]),
    );
  });

  it("asks Android for no media read access", () => {
    // Saving to the gallery is write-only and the photo picker needs no permission.
    expect(pluginOptions("expo-media-library").get("granularPermissions")).toEqual([]);
    expect(appJson.expo.android.blockedPermissions).toEqual(
      expect.arrayContaining([
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
        "android.permission.READ_MEDIA_AUDIO",
        "android.permission.READ_MEDIA_VISUAL_USER_SELECTED",
      ]),
    );
  });

  it("declares HTTPS-only encryption for export compliance", () => {
    expect(appJson.expo.ios.config.usesNonExemptEncryption).toBe(false);
  });
});
