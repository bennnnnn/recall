export function isLanguageProject(kind: string): boolean {
  return kind === "language" || kind === "vocabulary";
}

const STATUS_LABEL_KEYS: Record<string, string> = {
  mastered: "projects.status_mastered",
  learning: "projects.status_learning",
  new: "projects.status_new",
};

const STATUS_LABELS_EN: Record<string, string> = {
  mastered: "Mastered",
  learning: "Learning",
  new: "New",
};

/** Return the English label for a status (non-React callers). */
export function statusLabel(status: string): string {
  return STATUS_LABELS_EN[status] ?? STATUS_LABELS_EN.new;
}

/** Return the i18n'd label for a status (React components). */
export function statusLabelT(
  status: string,
  t: (key: string) => string,
): string {
  return t(STATUS_LABEL_KEYS[status] ?? STATUS_LABEL_KEYS.new);
}
