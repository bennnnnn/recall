import { deviceTimeZone } from "@/lib/datetime/phoneClock";

/**
 * IANA timezone from the device (e.g. America/New_York), for the server: the profile's
 * `timezone` and each chat turn's `client_timezone`. "UTC" when the engine cannot name
 * it; what the phone shows reads the zone in `lib/datetime/format.ts` instead.
 */
export function getDeviceTimezone(): string {
  return deviceTimeZone() ?? "UTC";
}
