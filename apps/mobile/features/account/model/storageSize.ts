/**
 * A Library size as Settings shows it: "120 MB", "1.2 GB", in the app's language
 * ("1,2 Go" in French). Sizes count in 1024s, as the server's plan totals do (400 MB, 4 GB).
 */
import type { Translate } from "@/lib/i18n/translate";
import { numberFormat } from "@/lib/money/format";

const KB = 1024;
const MB = KB * 1024;
const GB = MB * 1024;

/** One decimal below ten ("1.2 GB", "4 GB"), whole numbers from ten up ("120 MB"). */
function amount(value: number, locale: string): string {
  const digits = value < 10 ? 1 : 0;
  return numberFormat(locale, { maximumFractionDigits: digits }).format(value);
}

function formatStorageSize(bytes: number, locale: string, t: Translate): string {
  if (bytes >= GB) return t("settings.storage_gb", { size: amount(bytes / GB, locale) });
  // Under one MB but not empty: kilobytes, never "0 MB" for a Library that holds a file.
  if (bytes > 0 && bytes < MB) {
    return t("settings.storage_kb", { size: amount(Math.max(1, bytes / KB), locale) });
  }
  return t("settings.storage_mb", { size: amount(bytes / MB, locale) });
}

/** "120 MB of 400 MB". */
export function storageUsedOfTotal(
  usedBytes: number,
  limitBytes: number,
  locale: string,
  t: Translate,
): string {
  return t("settings.storage_value", {
    used: formatStorageSize(usedBytes, locale, t),
    total: formatStorageSize(limitBytes, locale, t),
  });
}
