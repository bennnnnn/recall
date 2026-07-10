/** Shared expo-print → native share helpers for PDF export. */

import * as Print from "expo-print";
import { Share } from "react-native";

export function isShareCancelled(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const message = "message" in error ? String((error as { message?: unknown }).message) : "";
  return /cancel|dismiss/i.test(message);
}

/** Render HTML to a PDF file and open the system share sheet. */
export async function printHtmlToSharedPdf(html: string, fileTitle: string): Promise<void> {
  const { uri } = await Print.printToFileAsync({ html });
  const title = fileTitle.endsWith(".pdf") ? fileTitle : `${fileTitle}.pdf`;
  try {
    const result = await Share.share({ url: uri, title });
    if (result.action === Share.dismissedAction) {
      return;
    }
  } catch (error) {
    if (isShareCancelled(error)) return;
    throw error;
  }
}
