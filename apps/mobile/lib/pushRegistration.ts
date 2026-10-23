/**
 * Whether the server holds this device's push token: reminders then come from the server,
 * and the phone schedules none of its own. Without one (Expo Go, no notification
 * permission, no EAS project, a failed registration, push switched off) the phone
 * schedules its reminders itself, so they still fire. No native module here: the to-do
 * context reads it without loading expo-notifications.
 */

let registered = false;
const listeners = new Set<() => void>();

export function setRemotePushRegistered(value: boolean): void {
  if (registered === value) return;
  registered = value;
  for (const listener of listeners) listener();
}

export function remotePushRegistered(): boolean {
  return registered;
}

export function subscribeRemotePushRegistered(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
