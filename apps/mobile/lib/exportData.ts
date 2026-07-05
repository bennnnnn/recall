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
