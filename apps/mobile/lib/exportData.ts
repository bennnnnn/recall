import {
  cacheDirectory,
  EncodingType,
  writeAsStringAsync,
} from "expo-file-system/legacy";
import { Share } from "react-native";

/** Pretty-print compact export JSON for sharing when the payload is small enough. */
export function formatExportJsonForShare(raw: string): string {
  const maxPrettyBytes = 500_000;
  if (raw.length > maxPrettyBytes) {
    return raw;
  }
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

export async function shareAccountExport(payload: string): Promise<void> {
  const dir = cacheDirectory;
  if (!dir) {
    await Share.share({ message: payload, title: "recall-export.json" });
    return;
  }

  const fileUri = `${dir}recall-export-${Date.now()}.json`;
  await writeAsStringAsync(fileUri, payload, { encoding: EncodingType.UTF8 });
  await Share.share({ url: fileUri, title: "recall-export.json" });
}
