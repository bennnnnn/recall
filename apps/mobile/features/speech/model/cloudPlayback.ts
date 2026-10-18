export function playbackStatusFinished(status: {
  didJustFinish?: boolean;
  currentTime?: number;
  duration?: number;
  playing?: boolean;
  sawPlaying?: boolean;
}): boolean {
  if (status.didJustFinish) return true;
  if (status.sawPlaying && status.playing === false) return true;
  const duration = status.duration ?? 0;
  const current = status.currentTime ?? 0;
  return duration > 0 && current >= duration - 0.04;
}
