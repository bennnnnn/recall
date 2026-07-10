/** Export a learning project (vocab / trivia / concepts) as a PDF. */

import type { ProjectDetail, ProjectItem, ProjectKind } from "@/lib/api";
import { escapeHtml, wrapPrintDocument } from "@/lib/printDocument";
import { isLanguageProject } from "@/lib/languageLevels";
import { isTriviaProject } from "@/lib/projectUi";

const STATUS_ORDER: Array<ProjectItem["status"]> = ["mastered", "learning", "new"];

export type ProjectPdfLabels = {
  mastered: string;
  learning: string;
  new: string;
  empty: string;
  definition: string;
  example: string;
  topic: string;
  summary: (counts: {
    total: number;
    mastered: number;
    learning: number;
    newCount: number;
  }) => string;
};

function flattenItems(project: ProjectDetail): ProjectItem[] {
  const seen = new Set<string>();
  const items: ProjectItem[] = [];
  for (const group of project.lists) {
    for (const item of group.items) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      items.push(item);
    }
  }
  return items;
}

function statusOf(item: ProjectItem): ProjectItem["status"] {
  if (item.status) return item.status;
  return item.mastered ? "mastered" : "new";
}

function renderItemHtml(item: ProjectItem, kind: ProjectKind, labels: ProjectPdfLabels): string {
  const title = escapeHtml(item.content.trim() || "—");
  const def = (item.definition || item.note || "").trim();
  const example = (item.example_sentence || "").trim();
  const topic = item.list_title?.trim();
  const bits: string[] = [`<div class="item"><h3>${title}</h3>`];
  if (isTriviaProject(kind) && topic && topic.toLowerCase() !== "general") {
    bits.push(`<p class="def"><strong>${escapeHtml(labels.topic)}:</strong> ${escapeHtml(topic)}</p>`);
  }
  if (def) {
    const label = isTriviaProject(kind) ? "" : `<strong>${escapeHtml(labels.definition)}:</strong> `;
    bits.push(`<p class="def">${label}${escapeHtml(def)}</p>`);
  }
  if (example && !isTriviaProject(kind)) {
    bits.push(
      `<p class="example"><strong>${escapeHtml(labels.example)}:</strong> ${escapeHtml(example)}</p>`,
    );
  }
  bits.push("</div>");
  return bits.join("");
}

export function projectLearningToPrintHtml(
  project: ProjectDetail,
  labels: ProjectPdfLabels,
): string {
  const items = flattenItems(project);
  const grouped: Record<ProjectItem["status"], ProjectItem[]> = {
    mastered: [],
    learning: [],
    new: [],
  };
  for (const item of items) {
    grouped[statusOf(item)].push(item);
  }

  const sectionTitle = (status: ProjectItem["status"]) => {
    if (status === "mastered") return labels.mastered;
    if (status === "learning") return labels.learning;
    return labels.new;
  };

  const bodyParts: string[] = [];
  for (const status of STATUS_ORDER) {
    const section = grouped[status];
    if (!section.length) continue;
    bodyParts.push(`<h2>${escapeHtml(sectionTitle(status))} (${section.length})</h2>`);
    for (const item of section) {
      bodyParts.push(renderItemHtml(item, project.kind, labels));
    }
  }
  if (!bodyParts.length) {
    bodyParts.push(`<p class="empty">${escapeHtml(labels.empty)}</p>`);
  }

  const meta = labels.summary({
    total: items.length,
    mastered: grouped.mastered.length,
    learning: grouped.learning.length,
    newCount: grouped.new.length,
  });

  const kindLabel = isTriviaProject(project.kind)
    ? "General knowledge"
    : isLanguageProject(project.kind)
      ? "Vocabulary"
      : "Learning";
  const title = `${project.title.trim() || "Learning"} — ${kindLabel}`;
  return wrapPrintDocument(title, bodyParts.join("\n"), meta);
}

export async function exportProjectAsPdf(
  project: ProjectDetail,
  labels: ProjectPdfLabels,
): Promise<void> {
  const { printHtmlToSharedPdf } = await import("@/lib/exportPdf");
  const html = projectLearningToPrintHtml(project, labels);
  const fileTitle = `${project.title.trim() || "learning"}-recall`;
  await printHtmlToSharedPdf(html, fileTitle);
}

export function projectHasExportableItems(project: ProjectDetail): boolean {
  return flattenItems(project).length > 0;
}
