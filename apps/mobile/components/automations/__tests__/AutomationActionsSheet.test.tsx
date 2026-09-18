import { fireEvent, render } from "@testing-library/react-native";

import { AutomationActionsSheet } from "@/components/automations/AutomationActionsSheet";

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
  status: "active" as const,
  onClose: jest.fn(),
  onEdit: jest.fn(),
  onShare: jest.fn(),
  onTogglePause: jest.fn(),
  onDelete: jest.fn(),
};

describe("AutomationActionsSheet", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows Pause by default for an active automation", async () => {
    const { getByText } = await render(<AutomationActionsSheet {...baseProps} />);
    expect(getByText("automations.pause")).toBeTruthy();
  });

  it("shows Resume for a paused automation", async () => {
    const { getByText } = await render(<AutomationActionsSheet {...baseProps} status="paused" />);
    expect(getByText("automations.resume")).toBeTruthy();
  });

  it("hides Pause/Resume for a completed automation", async () => {
    const { queryByText } = await render(
      <AutomationActionsSheet {...baseProps} status="completed" />,
    );
    expect(queryByText("automations.pause")).toBeNull();
    expect(queryByText("automations.resume")).toBeNull();
  });

  it("hides Pause/Resume when hideTogglePause is set (detail screen has a header icon instead)", async () => {
    const { queryByText } = await render(
      <AutomationActionsSheet {...baseProps} hideTogglePause />,
    );
    expect(queryByText("automations.pause")).toBeNull();
  });

  it("still offers Edit, Share, and Delete when hideTogglePause is set", async () => {
    const { getByText } = await render(<AutomationActionsSheet {...baseProps} hideTogglePause />);
    expect(getByText("automations.edit")).toBeTruthy();
    expect(getByText("automations.share")).toBeTruthy();
    expect(getByText("common.delete")).toBeTruthy();
  });

  it("calls onTogglePause when the row is pressed", async () => {
    const onTogglePause = jest.fn();
    const { getByText } = await render(
      <AutomationActionsSheet {...baseProps} onTogglePause={onTogglePause} />,
    );
    fireEvent.press(getByText("automations.pause"));
    expect(onTogglePause).toHaveBeenCalledTimes(1);
  });
});
