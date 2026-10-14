/** Shared expo-print → native share helpers for PDF export. */

import * as Print from "expo-print";

import { isShareCancelled } from "@/lib/shareCancelled";
import { shareLocalFile } from "@/lib/shareFile";

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
  // Through expo-sharing on Android: React Native's Share ignores `url` there
  // and would send nothing but the title.
  await shareLocalFile(uri, { title, mimeType: "application/pdf" });
}
