import { fireEvent, render } from "@testing-library/react-native";

import { LearningPathList } from "@/components/projects/LearningPathList";
import type { PathChapterProgress, ProjectListGroup } from "@/lib/api";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { chapter?: string; done?: number; total?: number; mastered?: number }) => {
      if (key === "projects.chapters_up_next") return `Up next: ${opts?.chapter ?? ""}`;
      if (key === "projects.chapters_progress") return `${opts?.done} / ${opts?.total} done`;
      if (key === "projects.journey_topic_progress") {
        return `${opts?.mastered}/${opts?.total} learned`;
      }
      return key;
    },
  }),
}));
jest.mock("@/components/ProjectItemRow", () => {
  const { Text } = require("react-native");
  return {
    ProjectItemRow: ({ item }: { item: { content: string } }) => <Text>{item.content}</Text>,
  };
});

const chapters: PathChapterProgress[] = [
  { title: "Greetings", mastered: 1, total: 2, complete: false },
  { title: "Food", mastered: 0, total: 0, complete: false },
];

const lists: ProjectListGroup[] = [
  {
    list_title: "Greetings",
    items: [
      {
        id: "w1",
        list_title: "Greetings",
        content: "hola",
        note: null,
        definition: "hello",
        example_sentence: null,
        status: "new",
        mastered: false,
        mastered_at: null,
        last_reviewed_at: null,
        review_count: 0,
        pronunciation_url: null,
        created_at: "2024-01-01T00:00:00Z",
      },
    ],
  },
];

describe("LearningPathList", () => {
  it("shows title-only empty path while chapters are still seeding", async () => {
    const { getByText, queryByText } = await render(
      <LearningPathList
        pathProgress={[]}
        lists={[]}
        speechLanguage="es-ES"
        busyId={null}
        onStatusChange={jest.fn()}
      />,
    );
    expect(getByText("projects.chapters_title")).toBeOnTheScreen();
    expect(getByText("projects.chapters_hint")).toBeOnTheScreen();
    expect(queryByText("Greetings")).toBeNull();
  });

  it("lists chapters and expands words for the current lesson", async () => {
    const { getByText } = await render(
      <LearningPathList
        pathProgress={chapters}
        upNext="Greetings"
        lists={lists}
        speechLanguage="es-ES"
        busyId={null}
        onStatusChange={jest.fn()}
      />,
    );
    expect(getByText("Greetings")).toBeOnTheScreen();
    expect(getByText("Food")).toBeOnTheScreen();
    expect(getByText("Up next: Greetings")).toBeOnTheScreen();
    expect(getByText("hola")).toBeOnTheScreen();
    fireEvent.press(getByText("Food"));
    expect(getByText("Food")).toBeOnTheScreen();
  });
});
