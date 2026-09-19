import { fireEvent, render } from "@testing-library/react-native";

import { JobSearchActionsSheet } from "@/components/jobSearch/JobSearchActionsSheet";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/lib/reduceMotion", () => ({
  useReduceMotion: () => false,
}));

const baseProps = {
  visible: true,
  paused: false,
  busy: false,
  onClose: jest.fn(),
  onEdit: jest.fn(),
  onTogglePause: jest.fn(),
  onShare: jest.fn(),
  onDelete: jest.fn(),
};

describe("JobSearchActionsSheet", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders edit, pause, share, and a danger delete row", async () => {
    const { getByText } = await render(<JobSearchActionsSheet {...baseProps} />);

    expect(getByText("my_job.edit")).toBeTruthy();
    expect(getByText("my_job.pause")).toBeTruthy();
    expect(getByText("my_job.share")).toBeTruthy();
    expect(getByText("common.delete")).toBeTruthy();
  });

  it("shows Resume instead of Pause when the search is paused", async () => {
    const { getByText, queryByText } = await render(
      <JobSearchActionsSheet {...baseProps} paused />,
    );

    expect(getByText("my_job.resume")).toBeTruthy();
    expect(queryByText("my_job.pause")).toBeNull();
  });

  it("routes each row to its handler", async () => {
    const { getByText } = await render(<JobSearchActionsSheet {...baseProps} />);

    await fireEvent.press(getByText("my_job.edit"));
    await fireEvent.press(getByText("my_job.pause"));
    await fireEvent.press(getByText("my_job.share"));
    await fireEvent.press(getByText("common.delete"));

    expect(baseProps.onEdit).toHaveBeenCalledTimes(1);
    expect(baseProps.onTogglePause).toHaveBeenCalledTimes(1);
    expect(baseProps.onShare).toHaveBeenCalledTimes(1);
    expect(baseProps.onDelete).toHaveBeenCalledTimes(1);
  });

  it("ignores pause and delete while busy", async () => {
    const { getByText } = await render(<JobSearchActionsSheet {...baseProps} busy />);

    await fireEvent.press(getByText("my_job.pause"));
    await fireEvent.press(getByText("common.delete"));

    expect(baseProps.onTogglePause).not.toHaveBeenCalled();
    expect(baseProps.onDelete).not.toHaveBeenCalled();
  });
});
