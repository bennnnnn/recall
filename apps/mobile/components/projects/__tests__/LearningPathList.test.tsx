import { fireEvent, render } from "@testing-library/react-native";

import { LearningPathList } from "@/components/projects/LearningPathList";
import type { DomainProgress } from "@/lib/projects/domainPath";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, opts?: { done?: number; total?: number; count?: number }) => {
      if (key === "projects.chapter_words") return `${opts?.done} / ${opts?.total} words`;
      if (key === "projects.group_review_meta") return `${opts?.count} words · Review`;
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

  it("shows the path as a list and only opens unlocked groups", async () => {
    const onOpenChapter = jest.fn();
    const { getByText, getAllByText, queryByText } = await render(
      <LearningPathList
        domains={domains}
        upNext="Hello and goodbye"
        onOpenChapter={onOpenChapter}
      />,
    );
    expect(getAllByText("Greetings").length).toBeGreaterThan(0);
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

  it("labels a completed group as review and still opens it", async () => {
    const onOpenChapter = jest.fn();
    const done: DomainProgress[] = [
      {
        title: "Hello",
        mastered: 16,
        total: 16,
        complete: true,
        chapters: [
          { title: "Hello", domain: "Hello", mastered: 16, total: 16, complete: true },
        ],
      },
    ];
    const { getByText } = await render(
      <LearningPathList domains={done} upNext={null} onOpenChapter={onOpenChapter} />,
    );
    expect(getByText("16 words · Review")).toBeOnTheScreen();
    fireEvent.press(getByText("Hello"));
    expect(onOpenChapter).toHaveBeenCalledWith("Hello");
  });
});
