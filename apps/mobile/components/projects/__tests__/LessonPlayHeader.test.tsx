import { fireEvent, render } from "@testing-library/react-native";

import { LessonPlayHeader } from "@/components/projects/LessonPlayHeader";

jest.mock("@/lib/motion", () => ({
  useReduceMotion: () => true,
  Motion: { duration: { short: 1, snappy: 1 }, easing: { out: undefined } },
}));

jest.mock("@/hooks/useResolvedColorScheme", () => ({
  useResolvedColorScheme: () => "light",
}));

jest.mock("@/components/Icon", () => ({ Icon: () => null }));

jest.mock("react-i18next", () => {
  const strings = require("@/lib/i18n/en.json");
  const t = (key: string, args: Record<string, unknown> = {}) =>
    String(strings[key] ?? key).replace(/{{(\w+)}}/g, (_: string, name: string) =>
      String(args[name] ?? ""),
    );
  return { useTranslation: () => ({ t }) };
});

it("puts close and the lesson menu above the progress counter", async () => {
  const onClose = jest.fn();
  const onOpenMenu = jest.fn();
  const { getByLabelText, getByText, getByRole } = await render(
    <LessonPlayHeader
      current={2}
      total={10}
      fill={0.2}
      reviewing={false}
      onClose={onClose}
      onOpenMenu={onOpenMenu}
    />,
  );

  expect(getByLabelText("Close")).toBeOnTheScreen();
  expect(getByLabelText("Lesson options")).toBeOnTheScreen();
  expect(getByText("2 of 10")).toBeOnTheScreen();
  expect(getByRole("progressbar")).toBeOnTheScreen();
  await fireEvent.press(getByLabelText("Lesson options"));
  expect(onOpenMenu).toHaveBeenCalled();
});
