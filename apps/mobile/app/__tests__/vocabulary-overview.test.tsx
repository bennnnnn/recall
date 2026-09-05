import React from "react";
import { act, fireEvent, render } from "@testing-library/react-native";
import VocabularyScreen from "@/app/projects/[id]/vocabulary";
import { LessonMapContent } from "@/app/projects/[id]/lesson";
import type { ProjectDetail } from "@/lib/api";
const mockRouter = { push: jest.fn() };
const mockAudio = { start: jest.fn(), stop: jest.fn() };
const mockLoad = jest.fn();
let mockCurrent = true;
const mockIsCurrent = () => mockCurrent;
let mockLoadError = false;
let mockProject: ProjectDetail;
const initial = () =>
  ({
    id: "p",
    kind: "language",
    target_language: "en",
    up_next: "Everyday expressions",
    daily_goal: 5,
    stats: { completed_today: 0 },
    path_progress: [
      {
        title: "Everyday expressions",
        domain: "Expressions",
        total: 1,
        mastered: 0,
        complete: false,
      },
      { title: "Everyday idioms", domain: "Idioms", total: 1, mastered: 0, complete: false },
    ],
    lists: [
      {
        list_title: "Everyday expressions",
        items: [
          {
            id: "by-the-way",
            content: "by the way",
            definition: "An expression used to introduce an additional thought or a new topic.",
            simple_gloss: "introducing another thought",
            example_sentences: [
              "By the way, your book is on the desk.",
              "The meeting went well; by the way, did you receive the notes?",
            ],
            part_of_speech: "phrase",
            vocabulary_kind: "expression",
          },
        ],
      },
      {
        list_title: "Everyday idioms",
        items: [
          {
            id: "break-the-ice",
            content: "break the ice",
            definition: "To make people feel more relaxed when they first meet.",
            example_sentences: [
              "We played a short game to break the ice.",
              "A friendly question can break the ice with new colleagues.",
            ],
            part_of_speech: "phrase",
            vocabulary_kind: "idiom",
          },
        ],
      },
    ],
  }) as ProjectDetail;
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => mockRouter,
  useLocalSearchParams: () => ({ id: "p" }),
}));
jest.mock("@/hooks/useAccountViewOwner", () => ({
  useAccountViewOwner: () => ({ key: "visit", isCurrent: mockIsCurrent }),
}));
jest.mock("@/hooks/useProjectDetail", () => ({
  useProjectDetail: () => ({
    project: mockProject,
    loading: false,
    loadError: mockLoadError,
    load: mockLoad,
    isCurrentOwner: mockIsCurrent,
  }),
}));
jest.mock("@/hooks/useLessonAudio", () => ({ useLessonAudio: () => mockAudio }));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token" }),
  useAuthToken: () => "token",
}));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("@/lib/pronunciation", () => ({ speakWord: jest.fn() }));
jest.mock("@/lib/auth", () => ({ getSessionGeneration: () => 1 }));
jest.mock("@shopify/flash-list", () => ({
  FlashList: jest.requireActual("react-native").FlatList,
}));
jest.mock("react-i18next", () => {
  const strings = require("@/lib/i18n/en.json");
  const t = (key: string, args: Record<string, unknown> = {}) =>
    String(strings[key] ?? key).replace(/{{(\w+)}}/g, (_: string, name: string) =>
      String(args[name] ?? ""),
    );
  return { useTranslation: () => ({ t }) };
});
beforeEach(() => {
  jest.clearAllMocks();
  mockProject = initial();
  mockCurrent = true;
  mockLoadError = false;
});
it("lists grouped vocabulary with full definitions, examples and pronunciation without mutation controls", async () => {
  const screen = await render(<VocabularyScreen />);
  expect(screen.getByText("Expressions")).toBeOnTheScreen();
  expect(screen.getByText("Everyday expressions")).toBeOnTheScreen();
  expect(
    screen.getByText("An expression used to introduce an additional thought or a new topic."),
  ).toBeOnTheScreen();
  expect(screen.getByText("By the way, your book is on the desk.")).toBeOnTheScreen();
  expect(
    screen.getByText("The meeting went well; by the way, did you receive the notes?"),
  ).toBeOnTheScreen();
  expect(screen.getByText("Everyday idioms")).toBeOnTheScreen();
  expect(screen.getByText("Idiom")).toBeOnTheScreen();
  await fireEvent.press(screen.getAllByLabelText("Play pronunciation")[0]);
  expect(mockAudio.start).toHaveBeenCalledWith("by the way", "en");
  expect(screen.queryByRole("button", { name: /edit|delete|master|continue/i })).toBeNull();
});
it("searches words and meanings, keeps matching group labels, and can clear an empty search", async () => {
  const screen = await render(<VocabularyScreen />);
  const input = screen.getByLabelText("Search words and meanings");
  await fireEvent.changeText(input, "break");
  expect(screen.getByRole("header", { name: "break the ice" })).toBeOnTheScreen();
  expect(screen.queryByRole("header", { name: "by the way" })).toBeNull();
  expect(screen.getByText("Everyday idioms")).toBeOnTheScreen();
  await fireEvent.changeText(input, "additional thought");
  expect(screen.getByRole("header", { name: "by the way" })).toBeOnTheScreen();
  expect(screen.queryByRole("header", { name: "break the ice" })).toBeNull();
  await fireEvent.changeText(input, "no matching word");
  expect(screen.getByText("No matching vocabulary")).toBeOnTheScreen();
  await fireEvent.press(screen.getByLabelText("Clear search"));
  expect(screen.getByRole("header", { name: "by the way" })).toBeOnTheScreen();
  expect(screen.getByRole("header", { name: "break the ice" })).toBeOnTheScreen();
});
it("renders only groups in the latest authoritative response", async () => {
  const screen = await render(<VocabularyScreen />);
  expect(screen.getByRole("header", { name: "by the way" })).toBeOnTheScreen();
  mockProject = {
    ...mockProject,
    lists: mockProject.lists.slice(1),
    path_progress: mockProject.path_progress?.slice(1),
  };
  await screen.rerender(<VocabularyScreen />);
  expect(screen.queryByRole("header", { name: "by the way" })).toBeNull();
  expect(screen.queryByText("Everyday expressions")).toBeNull();
  expect(screen.getByRole("header", { name: "break the ice" })).toBeOnTheScreen();
});
it("matches Spanish expressions without requiring accent marks", async () => {
  mockProject.target_language = "es";
  mockProject.lists = [
    {
      list_title: "Refranes",
      items: [
        {
          ...mockProject.lists[0].items[0],
          content: "más vale tarde que nunca",
          definition: "Es preferible hacer algo tarde a no hacerlo nunca.",
          example_sentences: [
            "Por fin terminé el curso: más vale tarde que nunca.",
            "Llegaste después de la comida, pero más vale tarde que nunca.",
          ],
          vocabulary_kind: "proverb",
        },
      ],
    },
  ];
  const screen = await render(<VocabularyScreen />);
  await fireEvent.changeText(screen.getByLabelText("Search words and meanings"), "mas vale");
  expect(screen.getByRole("header", { name: "más vale tarde que nunca" })).toBeOnTheScreen();
});
it("offers vocabulary from either language map independently of locked practice chapters", async () => {
  for (const language of ["en", "es"]) {
    mockProject.target_language = language;
    const screen = await render(<LessonMapContent isCurrent={mockIsCurrent} />);
    await fireEvent.press(screen.getByRole("button", { name: "Vocabulary" }));
    expect(mockRouter.push).toHaveBeenLastCalledWith("/projects/p/vocabulary");
    await screen.unmount();
  }
});
it("retained controls cannot speak, navigate or retry after leaving the account visit", async () => {
  mockLoadError = true;
  const screen = await render(<VocabularyScreen />);
  const speak = screen.getAllByLabelText("Play pronunciation")[0];
  const retry = screen.getByRole("button", { name: "Retry" });
  mockCurrent = false;
  await fireEvent.press(speak);
  await fireEvent.press(retry);
  expect(mockAudio.start).not.toHaveBeenCalled();
  expect(mockLoad).not.toHaveBeenCalled();
  await screen.unmount();
  mockCurrent = true;
  const map = await render(<LessonMapContent isCurrent={mockIsCurrent} />);
  mockCurrent = false;
  await fireEvent.press(map.getByRole("button", { name: "Vocabulary" }));
  expect(mockRouter.push).not.toHaveBeenCalled();
});
it("shows cached words alongside a retryable refresh error", async () => {
  mockLoadError = true;
  const screen = await render(<VocabularyScreen />);
  expect(screen.getByRole("header", { name: "by the way" })).toBeOnTheScreen();
  await act(() => fireEvent.press(screen.getByRole("button", { name: "Retry" })));
  expect(mockLoad).toHaveBeenCalledWith({ force: true });
});

it("gives an empty vocabulary response a real retry action", async () => {
  mockProject.lists = [];
  const screen = await render(<VocabularyScreen />);
  expect(screen.getByText("Vocabulary is not available yet.")).toBeOnTheScreen();
  await fireEvent.press(screen.getByRole("button", { name: "Retry" }));
  expect(mockLoad).toHaveBeenCalledWith({ force: true });
});
