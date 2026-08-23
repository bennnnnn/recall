import type { ProjectDetail, ProjectItem } from "@/lib/api";
import {
  chapterIsComplete,
  chapterItems,
  chapterQueue,
  itemToCard,
  overlayItemOutcomes,
  resolveLessonChapter,
} from "@/lib/projects/chapterLesson";

function item(content: string, status: ProjectItem["status"] = "new"): ProjectItem {
  return {
    id: content,
    list_title: "Greetings",
    content,
    note: null,
    definition: `def ${content}`,
    example_sentence: `ex ${content}`,
    status,
    mastered: status === "mastered",
    mastered_at: null,
    last_reviewed_at: null,
    review_count: 0,
    pronunciation_url: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const project = {
  up_next: "Hotel",
  path_progress: [
    { title: "Greetings", mastered: 1, total: 2, complete: false },
    { title: "Hotel", mastered: 0, total: 8, complete: false },
  ],
  lists: [
    { list_title: "Greetings", items: [item("hola"), item("adios", "mastered")] },
    { list_title: "Hotel", items: [item("llave")] },
  ],
} as ProjectDetail;

describe("chapterLesson", () => {
  it("picks items for a chapter and queues unmastered words first", () => {
    const items = chapterItems(project, "Greetings");
    expect(items.map((row) => row.content)).toEqual(["hola", "adios"]);
    expect(chapterQueue(items).map((row) => row.content)).toEqual(["hola"]);
  });

  it("caps the pending queue to the daily goal", () => {
    const items = [item("a"), item("b"), item("c"), item("d")];
    expect(chapterQueue(items, 2).map((row) => row.content)).toEqual(["a", "b"]);
  });

  it("treats a chapter complete only when every word is mastered", () => {
    const items = chapterItems(project, "Greetings");
    expect(chapterIsComplete(items)).toBe(false);
    expect(chapterIsComplete([item("hola", "mastered"), item("adios", "mastered")])).toBe(
      true,
    );
  });

  it("overlays in-session outcomes without waiting on the server", () => {
    const items = chapterItems(project, "Greetings");
    const next = overlayItemOutcomes(items, { hola: false });
    expect(chapterIsComplete(next)).toBe(true);
    expect(overlayItemOutcomes(items, { hola: true })[0]?.status).toBe("learning");
  });

  it("uses the requested chapter, then up next", () => {
    expect(resolveLessonChapter(project, "Greetings")).toBe("Greetings");
    expect(resolveLessonChapter(project, null)).toBe("Hotel");
  });

  it("maps an item onto a vocab card", () => {
    expect(itemToCard(item("hola"))).toEqual({
      word: "hola",
      definition: "def hola",
      exampleSentence: "ex hola",
    });
  });
});
