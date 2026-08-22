import { fireEvent, render } from "@testing-library/react-native";

import { LearningPathList } from "@/components/projects/LearningPathList";
import type { PathChapterProgress } from "@/lib/api";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { chapter?: string; done?: number; total?: number }) => {
      if (key === "projects.chapters_up_next") return `Up next: ${opts?.chapter ?? ""}`;
      if (key === "projects.chapters_progress") return `${opts?.done} / ${opts?.total} done`;
      return key;
    },
  }),
}));

const chapters: PathChapterProgress[] = [
  { title: "Greetings", mastered: 1, total: 2, complete: false },
  { title: "Food", mastered: 0, total: 0, complete: false },
];

describe("LearningPathList", () => {
  it("shows title-only empty path while chapters are still seeding", async () => {
    const { getByText, queryByText } = await render(
      <LearningPathList pathProgress={[]} onOpenSection={jest.fn()} />,
    );
    expect(getByText("projects.chapters_title")).toBeOnTheScreen();
    expect(queryByText("projects.chapters_hint")).toBeNull();
    expect(queryByText("Greetings")).toBeNull();
  });

  it("lists chapters and opens a section landing on tap", async () => {
    const onOpenSection = jest.fn();
    const { getByText } = await render(
      <LearningPathList
        pathProgress={chapters}
        upNext="Greetings"
        onOpenSection={onOpenSection}
      />,
    );
    expect(getByText("Greetings")).toBeOnTheScreen();
    expect(getByText("Food")).toBeOnTheScreen();
    expect(getByText("Up next: Greetings")).toBeOnTheScreen();
    fireEvent.press(getByText("Food"));
    expect(onOpenSection).toHaveBeenCalledWith("Food");
  });
});
