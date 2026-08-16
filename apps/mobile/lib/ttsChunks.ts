/** Split read-aloud text so the first OpenRouter TTS call is short. */

export const TTS_LEAD_MAX_CHARS = 220;
const TTS_LEAD_MIN_CHARS = 24;

export function splitTtsLead(plain: string): { lead: string; rest: string } {
  const normalized = plain.replace(/\s+/g, " ").trim();
  if (!normalized) return { lead: "", rest: "" };
  if (normalized.length <= TTS_LEAD_MAX_CHARS) {
    return { lead: normalized, rest: "" };
  }

  const window = normalized.slice(0, TTS_LEAD_MAX_CHARS);
  let cut = -1;
  for (let i = window.length - 1; i >= TTS_LEAD_MIN_CHARS; i -= 1) {
    const ch = window[i];
    if (ch === "." || ch === "!" || ch === "?" ) {
      cut = i + 1;
      break;
    }
  }
  if (cut < TTS_LEAD_MIN_CHARS) {
    cut = window.lastIndexOf(" ");
  }
  if (cut < TTS_LEAD_MIN_CHARS) {
    cut = TTS_LEAD_MAX_CHARS;
  }
  return {
    lead: normalized.slice(0, cut).trim(),
    rest: normalized.slice(cut).trim(),
  };
}
