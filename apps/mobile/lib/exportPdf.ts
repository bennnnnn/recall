/** Shared expo-print → native share helpers for PDF export. */

import * as Print from "expo-print";
import { Share } from "react-native";

import { isShareCancelled } from "@/lib/shareCancelled";

export { isShareCancelled };

/** Render HTML to a PDF file and open the system share sheet. */
export async function printHtmlToSharedPdf(
  html: string,
  fileTitle: string,
  isCurrent: () => boolean = () => true,
): Promise<void> {
  if (!isCurrent()) return;
  const { uri } = await Print.printToFileAsync({ html });
  if (!isCurrent()) return;
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
