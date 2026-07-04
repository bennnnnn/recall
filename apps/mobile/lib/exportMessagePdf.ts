import * as Print from "expo-print";
import { Share } from "react-native";

import { markdownToPrintHtml } from "@/lib/markdownPlain";

export async function exportMessageAsPdf(title: string, markdown: string): Promise<void> {
  const html = markdownToPrintHtml(title, markdown);
  const { uri } = await Print.printToFileAsync({ html });
  await Share.share({
    url: uri,
    title: title.endsWith(".pdf") ? title : `${title}.pdf`,
  });
}
