/** Local clock parts for an IANA timezone. */
export type ClockParts = {
  hours: number;
  minutes: number;
  seconds: number;
  dateLabel: string;
  timeLabel: string;
  displayTimeLabel: string;
  tzLabel: string;
};

export function prefers12hClock(locale: string | undefined): boolean {
  return (locale ?? "en").split("-")[0].toLowerCase() === "en";
}

export function resolveClockTimezone(
  content: string,
  fallback: string,
): string {
  const line = content.trim().split("\n")[0]?.trim() ?? "";
  if (line.includes("/") && !line.includes(":")) return line;
  return fallback.trim() || "UTC";
}

export function getClockParts(
  date: Date,
  timeZone: string,
  locale?: string,
): ClockParts {
  const timeFmt = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    hour12: false,
  });
  const dateFmt = new Intl.DateTimeFormat(locale || undefined, {
    timeZone,
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  const tzFmt = new Intl.DateTimeFormat(undefined, {
    timeZone,
    timeZoneName: "short",
  });

  const parts = timeFmt.formatToParts(date);
  const pick = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((p) => p.type === type)?.value ?? 0);

  const hours = pick("hour") % 12;
  const minutes = pick("minute");
  const seconds = pick("second");

  const tzParts = tzFmt.formatToParts(date);
  const tzLabel =
    tzParts.find((p) => p.type === "timeZoneName")?.value ?? timeZone;

  return {
    hours,
    minutes,
    seconds,
    dateLabel: dateFmt.format(date),
    timeLabel: `${String(pick("hour")).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`,
    displayTimeLabel: new Intl.DateTimeFormat(locale || undefined, {
      timeZone,
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: prefers12hClock(locale),
    }).format(date),
    tzLabel,
  };
}

/** Degrees from 12 o'clock, clockwise. */
export function handAngle(
  hours: number,
  minutes: number,
  seconds: number,
  kind: "hour" | "minute" | "second",
): number {
  if (kind === "second") return (seconds / 60) * 360;
  if (kind === "minute") return ((minutes + seconds / 60) / 60) * 360;
  return ((hours + minutes / 60 + seconds / 3600) / 12) * 360;
}
