/**
 * The Expo push token this install last registered with the server, kept on the device. A
 * sign-out hands the server this device's token so its reminders stop reaching this lock
 * screen, but with notifications turned off in the phone's Settings the token could no longer be
 * read (and the switch is no longer turned off on a refusal): the old account's token stayed on
 * the server, and once notifications were allowed again its reminders showed here. The token is
 * the install's, the same for every account, so it is not cleared at sign-out; it is forgotten
 * once the server has removed it (push switched off). Never registered: nothing is sent.
 */
import { createFilePref } from "@/lib/filePrefs";

const lastRegistered = createFilePref<string>(
  "recall.push-token.txt",
  (raw) => raw?.trim() ?? "",
  (token) => token,
);

/** A read or write that fails reads as none, or keeps the value in memory for this run
 * (`lib/filePrefs.ts`): neither throws. */
export async function readRegisteredPushToken(): Promise<string | null> {
  return (await lastRegistered.get()) || null;
}

export function rememberRegisteredPushToken(token: string | null): Promise<void> {
  return lastRegistered.set(token ?? "");
}
