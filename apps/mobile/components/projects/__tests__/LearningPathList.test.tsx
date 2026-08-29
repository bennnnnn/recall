import { fireEvent, render } from "@testing-library/react-native";

import { LearningPathList } from "@/components/projects/LearningPathList";
import type { DomainProgress } from "@/lib/projects/domainPath";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { done?: number; total?: number }) => {
      if (key === "projects.chapter_words") return `${opts?.done} / ${opts?.total} words`;
      return key;
    },
  }),
}));

const domains: DomainProgress[] = [
  {
    title: "Greetings",
    mastered: 1,
    total: 13,
    complete: false,
    chapters: [
      { title: "Hello and goodbye", domain: "Greetings", mastered: 1, total: 13, complete: false },
      { title: "Courtesy", domain: "Greetings", mastered: 0, total: 12, complete: false },
    ],
  },
  {
    title: "Family",
    mastered: 0,
    total: 24,
    complete: false,
    chapters: [
      { title: "Immediate family", domain: "Family", mastered: 0, total: 12, complete: false },
    ],
  },
];

describe("LearningPathList", () => {
  it("renders nothing while domains are still seeding", async () => {
    const { queryByText } = await render(
      <LearningPathList domains={[]} onOpenChapter={jest.fn()} />,
    );
    expect(queryByText("Greetings")).toBeNull();
  });

  it("shows the path of circular nodes and only opens unlocked chapters", async () => {
    const onOpenChapter = jest.fn();
    const { getByText, queryByText } = await render(
      <LearningPathList
        domains={domains}
        upNext="Hello and goodbye"
        onOpenChapter={onOpenChapter}
      />,
    );
    expect(getByText("Greetings")).toBeOnTheScreen();
    expect(getByText("Hello and goodbye")).toBeOnTheScreen();
    expect(getByText("Courtesy")).toBeOnTheScreen();
    expect(getByText("Immediate family")).toBeOnTheScreen();
    expect(queryByText("Up next: Hello and goodbye")).toBeNull();
    fireEvent.press(getByText("Hello and goodbye"));
    expect(onOpenChapter).toHaveBeenCalledWith("Hello and goodbye");
    fireEvent.press(getByText("Courtesy"));
    fireEvent.press(getByText("Immediate family"));
    expect(onOpenChapter).toHaveBeenCalledTimes(1);
  });
});
