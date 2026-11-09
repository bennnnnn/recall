import type { EmailDraft } from "@/lib/richBlocks";

export function fullEmailText(draft: EmailDraft): string {
  const parts: string[] = [];
  if (draft.to) parts.push(`To: ${draft.to}`);
  if (draft.subject) parts.push(`Subject: ${draft.subject}`);
  if (parts.length) parts.push("");
  parts.push(draft.body);
  return parts.join("\n");
}

/**
 * A query string with every value percent-encoded, a space as `%20`. URLSearchParams (React
 * Native's too) writes a space as `+`, which only form decoders read back as a space; a
 * strict URL reader (iOS's URLComponents, as an app reads its link) keeps the `+`.
 */
function composeQuery(fields: [string, string | undefined][]): string {
  return fields
    .filter((field): field is [string, string] => Boolean(field[1]))
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join("&");
}

/** Gmail web compose — opens Gmail app on mobile when installed. */
export function buildGmailComposeUrl(draft: EmailDraft): string {
  const query = composeQuery([
    ["view", "cm"],
    ["fs", "1"],
    ["to", draft.to?.trim()],
    ["su", draft.subject?.trim()],
    ["body", draft.body.trim()],
  ]);
  return `https://mail.google.com/mail/?${query}`;
}

/** Gmail iOS/Android app compose deep link. */
export function buildGmailAppComposeUrl(draft: EmailDraft): string {
  const query = composeQuery([
    ["to", draft.to?.trim()],
    ["subject", draft.subject?.trim()],
    ["body", draft.body.trim()],
  ]);
  return query ? `googlegmail:///co?${query}` : "googlegmail:///co";
}

export function gmailComposeCandidates(draft: EmailDraft): string[] {
  return [buildGmailAppComposeUrl(draft), buildGmailComposeUrl(draft)];
}
