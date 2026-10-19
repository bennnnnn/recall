/**
 * The time on a reminder card, in the zone the server read the user's words in.
 *
 * "Remind me at 9am" said while the phone is in New York and the account is in
 * Nairobi is 9:00 AM Nairobi time: the reply says "9 AM", and a card drawn in
 * the phone's own zone said "2:00 AM" with nothing to say why. The card now
 * shows the server's zone, and names it when the phone shows another time.
 */

import {
  formatClockTime,
  formatShortWeekdayDate,
  formatTimeZoneName,
} from "@/lib/datetime/format";
import { getDeviceTimezone } from "@/lib/deviceTimezone";

/** "Thu, Oct 15, 9:00 AM", or "Thu, Oct 15, 9:00 AM GMT+3" when the phone is elsewhere. */
export function proposalDueLabel(
  due: Date,
  timeZone: string | null,
  deviceZone: string = getDeviceTimezone(),
): string {
  const zone = timeZone && formatTimeZoneName(due, timeZone) ? timeZone : undefined;
  const when = wallClock(due, zone);
  if (!zone || zone === deviceZone || when === wallClock(due, deviceZone)) return when;
  return `${when} ${formatTimeZoneName(due, zone)}`;
}

function wallClock(due: Date, zone: string | undefined): string {
  return `${formatShortWeekdayDate(due, undefined, zone)}, ${formatClockTime(due, undefined, zone)}`;
}
