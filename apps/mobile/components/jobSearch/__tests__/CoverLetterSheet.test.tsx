import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { Alert, StyleSheet } from "react-native";

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

beforeEach(() => {
  jest.clearAllMocks();
  mockShare.mockResolvedValue({});
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

afterEach(() => jest.restoreAllMocks());

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

test("does not alert when the share helper consumes cancellation", async () => {
  const { getByText } = await render(
    <CoverLetterSheet visible loading={false} letter="Dear team, ..." onClose={jest.fn()} />,
  );
  await fireEvent.press(getByText("my_job.cover_letter_share"));
  await waitFor(() => expect(mockShare).toHaveBeenCalledTimes(1));
  expect(Alert.alert).not.toHaveBeenCalled();
});

test("alerts a localized failure when sharing throws", async () => {
  mockShare.mockRejectedValue(new Error("native failure"));
  const { getByText } = await render(
    <CoverLetterSheet visible loading={false} letter="Dear team, ..." onClose={jest.fn()} />,
  );
  await fireEvent.press(getByText("my_job.cover_letter_share"));
  await waitFor(() =>
    expect(Alert.alert).toHaveBeenCalledWith("common.share_failed", "my_job.share_failed"),
  );
});

test("uses a minimum 44 point close target", async () => {
  const { getAllByLabelText } = await render(
    <CoverLetterSheet visible loading={false} letter="Dear team, ..." onClose={jest.fn()} />,
  );
  expect(
    getAllByLabelText("common.close").some((button) => {
      const style = StyleSheet.flatten(button.props.style);
      return style.width === 44 && style.height === 44;
    }),
  ).toBe(true);
});
