import { Redirect, useLocalSearchParams } from "expo-router";

import { lessonMapPath } from "@/lib/projects/chapterAccess";

/** Thin redirect — the stats screen is retired from the main flow. */
export default function ProjectDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  if (typeof id !== "string") return <Redirect href="/projects" />;
  return <Redirect href={lessonMapPath(id)} />;
}
