import { fireEvent, render, waitFor } from "@testing-library/react-native";

import { CoverLetterSheet } from "@/components/jobSearch/CoverLetterSheet";

const mockSetString = jest.fn(async () => {});
const mockShare = jest.fn(async () => ({}));

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-clipboard", () => ({
  setStringAsync: (...args: unknown[]) => mockSetString(...args),
}));
jest.mock("@/lib/share", () => ({
  presentShareSheet: (...args: unknown[]) => mockShare(...args),
}));
jest.mock("@/lib/haptics", () => ({ tap: jest.fn() }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

test("shows a loading state while generating", async () => {
  const { getByText, queryByText } = await render(
    <CoverLetterSheet visible loading letter={null} onClose={jest.fn()} />,
  );
  expect(getByText("my_job.cover_letter_generating")).toBeTruthy();
  expect(queryByText("common.copy")).toBeNull();
});

test("renders the letter and copies it", async () => {
  const { getByText } = await render(
    <CoverLetterSheet visible loading={false} letter="Dear team, ..." onClose={jest.fn()} />,
  );
  expect(getByText("Dear team, ...")).toBeTruthy();
  await fireEvent.press(getByText("common.copy"));
  await waitFor(() => expect(mockSetString).toHaveBeenCalledWith("Dear team, ..."));
});

test("shares the letter and keeps the sheet open until share returns", async () => {
  let resolveShare: (value: object) => void = () => {};
  mockShare.mockImplementation(
    () => new Promise<object>((resolve) => (resolveShare = resolve)),
  );
  const onClose = jest.fn();
  const { getByText } = await render(
    <CoverLetterSheet visible loading={false} letter="Dear team, ..." onClose={onClose} />,
  );
  await fireEvent.press(getByText("my_job.cover_letter_share"));
  expect(mockShare).toHaveBeenCalledWith({ message: "Dear team, ..." });
  resolveShare({});
  await waitFor(() => expect(mockShare).toHaveBeenCalledTimes(1));
  expect(onClose).not.toHaveBeenCalled();
});
