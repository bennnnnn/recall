import * as Clipboard from "expo-clipboard";

type ClipboardWithImage = typeof Clipboard & {
  hasImageAsync?: () => Promise<boolean>;
};

/** The clipboard's text handed to `paste`, when there is any (the math pad's Paste key). */
export function pasteClipboardText(paste: (text: string) => unknown): void {
  void Clipboard.getStringAsync().then((text) => {
    if (text) void paste(text);
  });
}

/** True when the clipboard is an image with no usable text layer. */
export async function clipboardIsImageOnly(): Promise<boolean> {
  try {
    const clip = Clipboard as ClipboardWithImage;
    if (typeof clip.hasImageAsync !== "function") return false;
    const hasImage = await clip.hasImageAsync();
    if (!hasImage) return false;
    const text = (await Clipboard.getStringAsync()).trim();
    return text.length === 0;
  } catch {
    return false;
  }
}
