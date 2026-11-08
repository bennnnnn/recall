/** Hand a local file to the system share sheet on iOS and Android. */

import { Platform, Share } from "react-native";

import { isShareCancelled } from "@/lib/shareCancelled";
import { SharingUnavailableError } from "@/lib/shareUnavailable";

type SharingModule = {
  shareAsync: (url: string, options?: { mimeType?: string; UTI?: string; dialogTitle?: string }) => Promise<void>;
};

/**
 * expo-sharing, when this build has its native module. Loaded lazily: its JS
 * calls requireNativeModule on import, so a dev client built before it was
 * added would otherwise crash every screen that can share.
 */
function loadSharing(): SharingModule | null {
  try {
    const { requireOptionalNativeModule } =
      // eslint-disable-next-line @typescript-eslint/no-require-imports -- lazy, like expo-sharing below
      require("expo-modules-core") as typeof import("expo-modules-core");
    if (!requireOptionalNativeModule("ExpoSharing")) return null;
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- only once its native module is in this build
    return require("expo-sharing") as SharingModule;
  } catch {
    return null;
  }
}

type ShareRoute = "expo-sharing" | "rn-share" | "unavailable";

/**
 * How a file reaches the share sheet. expo-sharing hands over the file on
 * both platforms. React Native's Share sends a file only on iOS (`url`);
 * Android ignores `url` and would send the cache path as text, so Android
 * without expo-sharing cannot share a file at all.
 */
export function shareRoute(platform: string, hasSharing: boolean): ShareRoute {
  if (hasSharing) return "expo-sharing";
  return platform === "ios" ? "rn-share" : "unavailable";
}

/** The URI's file name ends in an extension: `photo.jpg`, `Scan.PDF`. */
function hasExtension(uri: string): boolean {
  const name = uri.split(/[?#]/)[0]!.split("/").pop() ?? "";
  return /.\.[A-Za-z0-9]{1,10}$/.test(name);
}

/**
 * The type expo-sharing is told. Android sends it as the intent's type. The iOS sheet reads the
 * type from the file's extension, and expo-sharing uses a declared one only to rename the file
 * to that type's preferred extension: "photo.jpg" went out as "photo.jpg.jpeg" and "Scan.PDF"
 * as "Scan.PDF.pdf". So iOS declares one only for a file with no extension; without it such a
 * file (a PDF among them) would open as plain data.
 */
function declaredType(
  platform: string,
  localUri: string,
  options: { mimeType?: string | null; uti?: string },
): { mimeType?: string; UTI?: string } {
  if (platform === "ios" && hasExtension(localUri)) return {};
  return {
    ...(options.mimeType ? { mimeType: options.mimeType } : {}),
    ...(options.uti ? { UTI: options.uti } : {}),
  };
}

/** A file share is running: from the tap, through any download or print, until its sheet closes. */
let shareInFlight = false;

/**
 * Run one file share at a time, app-wide. Android's share module takes one request until
 * its sheet closes and refuses the next ("Another share request is being processed now"),
 * so a second tap on Share while a PDF downloaded said the export failed. A share asked
 * for while one runs is dropped: false. Every Share button and export goes through here.
 */
export async function shareOneAtATime(share: () => Promise<void>): Promise<boolean> {
  if (shareInFlight) return false;
  shareInFlight = true;
  try {
    await share();
    return true;
  } finally {
    shareInFlight = false;
  }
}

/**
 * Open the share sheet for a `file://` URI. A dismissed sheet is not an
 * error; a build that cannot share a file on this platform throws `SharingUnavailableError`.
 */
export async function shareLocalFile(
  localUri: string,
  options: { title: string; mimeType?: string | null; uti?: string },
): Promise<void> {
  const sharing = loadSharing();
  const route = shareRoute(Platform.OS, sharing != null);
  if (route === "unavailable") {
    throw new SharingUnavailableError();
  }
  try {
    if (route === "expo-sharing" && sharing) {
      await sharing.shareAsync(localUri, { dialogTitle: options.title, ...declaredType(Platform.OS, localUri, options) });
    } else {
      await Share.share({ url: localUri, title: options.title });
    }
  } catch (error) {
    if (isShareCancelled(error)) return;
    throw error;
  }
}
