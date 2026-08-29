import type { ProjectDetail, ProjectItem } from "@/lib/api";
import {
  chapterIsComplete,
  chapterItems,
  chapterQueue,
  exampleSentences,
  highlightLemmaParts,
  isChapterReview,
  itemToCard,
  overlayMasteredItems,
  groupLessonProgress,
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

  it("queues learning words before new ones", () => {
    const items = [item("new"), item("retry", "learning"), item("fresh")];
    expect(chapterQueue(items).map((row) => row.content)).toEqual(["retry", "new", "fresh"]);
  });

  it("caps the pending queue to the daily goal so a sitting is not the whole chapter", () => {
    const items = [item("a"), item("b"), item("c"), item("d")];
    expect(chapterQueue(items, 2).map((row) => row.content)).toEqual(["a", "b"]);
  });

  it("replays a finished chapter as an uncapped review", () => {
    const items = [
      item("a", "mastered"),
      item("b", "mastered"),
      item("c", "mastered"),
    ];
    expect(isChapterReview(items)).toBe(true);
    expect(chapterQueue(items, 2).map((row) => row.content)).toEqual(["a", "b", "c"]);
  });

  it("treats a chapter complete only when every word is mastered", () => {
    const items = chapterItems(project, "Greetings");
    expect(chapterIsComplete(items)).toBe(false);
    expect(chapterIsComplete([item("hola", "mastered"), item("adios", "mastered")])).toBe(
      true,
    );
  });

  it("overlays in-session known marks without waiting on the server", () => {
    const items = chapterItems(project, "Greetings");
    const next = overlayMasteredItems(items, { hola: true });
    expect(chapterIsComplete(next)).toBe(true);
    expect(overlayMasteredItems(items, {})[0]?.status).toBe("new");
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
    expect(
      itemToCard({
        ...item("resilient"),
        ipa: "rɪˈzɪliənt",
        part_of_speech: "adjective",
        simple_gloss: "you bounce back",
      }),
    ).toEqual({
      word: "resilient",
      definition: "def resilient",
      exampleSentence: "ex resilient",
      ipa: "rɪˈzɪliənt",
      partOfSpeech: "adjective",
      simpleGloss: "you bounce back",
    });
  });

  it("highlights the lemma inside an example", () => {
    expect(highlightLemmaParts("She stayed resilient after losing her job.", "resilient")).toEqual(
      [
        { text: "She stayed ", match: false },
        { text: "resilient", match: true },
        { text: " after losing her job.", match: false },
      ],
    );
  });

  it("splits at most two example sentences", () => {
    expect(exampleSentences("See you later.\nSee you tomorrow.\nExtra.")).toEqual([
      "See you later.",
      "See you tomorrow.",
    ]);
    expect(exampleSentences("  only one  ")).toEqual(["only one"]);
  });

  it("counts progress against the group, not the daily batch", () => {
    const items = [
      item("a", "mastered"),
      item("b", "mastered"),
      item("c"),
      item("d"),
      item("e"),
    ];
    expect(groupLessonProgress(items, "c")).toEqual({
      current: 3,
      total: 5,
      fill: 2 / 5,
    });
    expect(groupLessonProgress(items, null)).toEqual({
      current: 2,
      total: 5,
      fill: 2 / 5,
    });
  });

  it("uses place-in-group during review of a finished chapter", () => {
    const items = [
      item("a", "mastered"),
      item("b", "mastered"),
      item("c", "mastered"),
    ];
    expect(groupLessonProgress(items, "b")).toEqual({
      current: 2,
      total: 3,
      fill: 2 / 3,
    });
  });
});
