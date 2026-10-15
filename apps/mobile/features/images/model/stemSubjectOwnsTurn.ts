import { api } from "@/lib/api";

/**
 * True when the server leaves this composer turn to maths, physics or chemistry.
 *
 * The shared text rules (imageGenIntent.ts) read "draw ethanol" or "A lens has
 * focal length 15 cm. Where's the image?" as picture requests. The phone has no
 * subject detector, so before it calls /images/generate it asks the server
 * (POST /images/intent), which answers with the same `stem_subject` its chat
 * path checks before its own image intercept. Any failure keeps the phone's own
 * reading: a picture.
 */
export async function stemSubjectOwnsTurn(
  token: string | null,
  text: string,
): Promise<boolean> {
  if (!token) return false;
  try {
    const { subject } = await api.imageIntent(token, text);
    return subject != null;
  } catch {
    return false;
  }
}
