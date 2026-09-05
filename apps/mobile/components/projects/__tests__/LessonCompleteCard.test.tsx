import { render } from "@testing-library/react-native";

import { LessonCompleteCard } from "@/components/projects/LessonCompleteCard";

jest.mock("@/lib/motion", () => ({
  useReduceMotion: () => true,
  Motion: { duration: { snappy: 1 }, easing: { out: undefined } },
}));

jest.mock("@/hooks/useResolvedColorScheme", () => ({
  useResolvedColorScheme: () => "light",
}));

jest.mock("@/lib/haptics", () => ({ notifySuccess: jest.fn() }));

jest.mock("@/components/Icon", () => ({ Icon: () => null }));

jest.mock("react-i18next", () => {
  const strings = require("@/lib/i18n/en.json");
  const t = (key: string, args: Record<string, string> = {}) =>
    String(strings[key] ?? key).replace(/{{(\w+)}}/g, (_: string, name: string) => args[name] ?? "");
  return { useTranslation: () => ({ t }) };
});

it("names the group the learner just finished", async () => {
  const { getByText, getByTestId, rerender, queryByText } = await render(
    <LessonCompleteCard title="Greetings" reviewing={false} groupDone />,
  );
  expect(getByText("Greetings complete")).toBeOnTheScreen();
  expect(getByTestId("lesson-complete-burst")).toBeOnTheScreen();
  expect(queryByText("Practice complete")).toBeNull();

  await rerender(<LessonCompleteCard title="Greetings" reviewing groupDone />);
  expect(getByText("Greetings review complete")).toBeOnTheScreen();
});
