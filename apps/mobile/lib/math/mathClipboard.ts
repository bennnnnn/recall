import * as Clipboard from "expo-clipboard";

type ClipboardWithImage = typeof Clipboard & {
  hasImageAsync?: () => Promise<boolean>;
};

/** True when the clipboard is an image with no usable text layer. */
export async function clipboardIsImageOnly(): Promise<boolean> {
  try {
    const text = (await Clipboard.getStringAsync()).trim();
    if (text.length > 0) return false;
    const clip = Clipboard as ClipboardWithImage;
    if (typeof clip.hasImageAsync !== "function") return false;
    return await clip.hasImageAsync();
  } catch {
    return false;
  }
}
