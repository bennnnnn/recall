import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { LearningPathList } from "@/components/projects/LearningPathList";
import type { DomainProgress } from "@/lib/projects/domainPath";
import { resetMapUnlockState } from "@/lib/projects/mapUnlock";

jest.mock("@/lib/motion", () => ({
  useReduceMotion: () => true,
  Motion: {
    duration: { soft: 1 },
    easing: { inOut: undefined },
  },
}));

jest.mock("@/hooks/useResolvedColorScheme", () => ({
  useResolvedColorScheme: () => "light",
}));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
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
  beforeEach(() => {
    resetMapUnlockState();
  });
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

  it("springs the check once when a group becomes done after the map was seeded", async () => {
    const onOpenChapter = jest.fn();
    const current: DomainProgress[] = [
      {
        title: "Hello",
        mastered: 16,
        total: 16,
        complete: true,
        chapters: [{ title: "Hello", domain: "Hello", mastered: 16, total: 16, complete: true }],
      },
      {
        title: "Morning",
        mastered: 4,
        total: 10,
        complete: false,
        chapters: [
          { title: "Morning", domain: "Morning", mastered: 4, total: 10, complete: false },
        ],
      },
    ];
    const finished: DomainProgress[] = [
      current[0],
      {
        title: "Morning",
        mastered: 10,
        total: 10,
        complete: true,
        chapters: [
          { title: "Morning", domain: "Morning", mastered: 10, total: 10, complete: true },
        ],
      },
    ];
    const screen = await render(
      <LearningPathList
        domains={current}
        projectId="p"
        upNext="Morning"
        onOpenChapter={onOpenChapter}
      />,
    );
    expect(screen.getByTestId("path-node-current")).toBeOnTheScreen();
    expect(screen.queryByTestId("path-node-unlock")).toBeNull();

    await screen.rerender(
      <LearningPathList
        domains={finished}
        projectId="p"
        upNext={null}
        onOpenChapter={onOpenChapter}
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("path-node-unlock")).toBeOnTheScreen();
    });
    await screen.unmount();

    const again = await render(
      <LearningPathList
        domains={finished}
        projectId="p"
        upNext={null}
        onOpenChapter={onOpenChapter}
      />,
    );
    expect(again.queryByTestId("path-node-unlock")).toBeNull();
    expect(again.queryByTestId("path-node-current")).toBeNull();
  });

  it("does not pulse any node when every group is already done", async () => {
    const done: DomainProgress[] = [
      {
        title: "Useful conversation expressions",
        mastered: 10,
        total: 10,
        complete: true,
        chapters: [
          {
            title: "Useful conversation expressions",
            domain: "Useful conversation expressions",
            mastered: 10,
            total: 10,
            complete: true,
          },
        ],
      },
      {
        title: "Everyday phrasal verbs",
        mastered: 10,
        total: 10,
        complete: true,
        chapters: [
          {
            title: "Everyday phrasal verbs",
            domain: "Everyday phrasal verbs",
            mastered: 10,
            total: 10,
            complete: true,
          },
        ],
      },
      {
        title: "Everyday idioms",
        mastered: 10,
        total: 10,
        complete: true,
        chapters: [
          {
            title: "Everyday idioms",
            domain: "Everyday idioms",
            mastered: 10,
            total: 10,
            complete: true,
          },
        ],
      },
      {
        title: "Common proverbs",
        mastered: 10,
        total: 10,
        complete: true,
        chapters: [
          {
            title: "Common proverbs",
            domain: "Common proverbs",
            mastered: 10,
            total: 10,
            complete: true,
          },
        ],
      },
    ];
    const { queryByTestId } = await render(
      <LearningPathList domains={done} projectId="p" upNext={null} onOpenChapter={jest.fn()} />,
    );
    expect(queryByTestId("path-node-current")).toBeNull();
    expect(queryByTestId("path-node-unlock")).toBeNull();
  });
});
