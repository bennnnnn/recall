import { Alert } from "react-native";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import DataControlsScreen from "@/features/account/screens/DataControlsScreen";

const mockUpdateUser = jest.fn();
const mockLocationLabel = jest.fn();
const mockConfirm = jest.fn();
const mockExport = jest.fn();
const mockCancelExport = jest.fn();
const mockDeleteAccount = jest.fn();
const mockDeleteAllChats = jest.fn();
const mockReplace = jest.fn();
const mockReportError = jest.fn();
let mockProgress = "idle";
let mockUser: Record<string, unknown>;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({
  Redirect: () => null,
  router: { push: jest.fn() },
  useRouter: () => ({ replace: mockReplace }),
  useNavigation: () => ({ setOptions: jest.fn() }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: mockUser, updateUser: mockUpdateUser }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/features/account/hooks/useDataControls", () => ({
  useDataControls: () => ({
    progress: mockProgress,
    exportData: mockExport,
    cancelExport: mockCancelExport,
    deleteAccount: mockDeleteAccount,
  }),
}));
jest.mock("@/lib/api", () => ({
  api: { archiveAllChats: jest.fn(), deleteAllChats: (...args: unknown[]) => mockDeleteAllChats(...args) },
}));
jest.mock("@/ui/overlay/dialogs", () => ({
  confirmDialog: (...args: unknown[]) => mockConfirm(...args),
  alertDialog: jest.fn(),
}));
jest.mock("@/lib/cache/chatListCache", () => ({ invalidateChatListCache: jest.fn() }));
jest.mock("@/lib/reportRecoverableError", () => ({
  reportRecoverableError: (...args: unknown[]) => mockReportError(...args),
}));
jest.mock("@/lib/deviceLocation", () => ({
  getDeviceLocationLabel: (...args: unknown[]) => mockLocationLabel(...args),
}));
jest.mock("@/lib/expoRuntime", () => ({ canUseDeviceLocation: () => true }));
jest.mock("@/ui/controls/StackBackButton", () => ({
  StackBackButton: () => null,
  plainHeaderItems: () => [],
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockUser = { name: "bini", location: null, location_enabled: false };
  mockUpdateUser.mockResolvedValue(undefined);
  mockConfirm.mockResolvedValue(true);
  mockExport.mockResolvedValue(true);
  mockDeleteAllChats.mockResolvedValue(undefined);
  mockProgress = "idle";
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
});

it("opens with web search (on by default) and location, no explanation lines", async () => {
  const view = await render(<DataControlsScreen />);
  const search = view.getByRole("switch", { name: "settings.web_search" });
  expect(search.props.accessibilityState.checked).toBe(true);
  expect(view.getByText("settings.use_current_location")).toBeTruthy();
  expect(view.queryByText("settings.web_search_summary")).toBeNull();
  expect(view.queryByText("settings.location_summary")).toBeNull();
  // The policy itself lives once, under About.
  expect(view.queryByText("privacy.title")).toBeNull();
});

it("turns web search off for the account", async () => {
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByRole("switch", { name: "settings.web_search" }));
  await waitFor(() => expect(mockUpdateUser).toHaveBeenCalledWith({ web_search_enabled: false }));
});

it("turns location on with the device's place", async () => {
  mockLocationLabel.mockResolvedValue("Addis Ababa, Ethiopia");
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByRole("switch", { name: "settings.use_current_location" }));
  await waitFor(() =>
    expect(mockUpdateUser).toHaveBeenCalledWith({
      location_enabled: true,
      location: "Addis Ababa, Ethiopia",
    }),
  );
});

it("clears all chats only after a confirmation that says what stays", async () => {
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByText("settings.delete_all_chats"));
  await waitFor(() => expect(mockDeleteAllChats).toHaveBeenCalledWith("tok"));
  expect(mockConfirm).toHaveBeenCalledWith(
    expect.objectContaining({
      title: "settings.delete_all_chats_title",
      message: "settings.delete_all_chats_body",
      destructive: true,
    }),
  );
});

it("keeps every chat when the clear is cancelled", async () => {
  mockConfirm.mockResolvedValue(false);
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByText("settings.delete_all_chats"));
  await waitFor(() => expect(mockConfirm).toHaveBeenCalled());
  expect(mockDeleteAllChats).not.toHaveBeenCalled();
});

it("exports only after a confirmation that says what the file holds", async () => {
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByText("settings.export"));
  await waitFor(() => expect(mockExport).toHaveBeenCalled());
  expect(mockConfirm).toHaveBeenCalledWith(
    expect.objectContaining({ title: "settings.export_confirm_title", message: "settings.export_confirm_body" }),
  );
});

it("shows the export in progress with a way to cancel it", async () => {
  mockProgress = "exporting";
  const view = await render(<DataControlsScreen />);
  expect(view.getByText("settings.export_progress")).toBeTruthy();
  await fireEvent.press(view.getByText("common.cancel"));
  expect(mockCancelExport).toHaveBeenCalled();
});

it("deletes the account only after a confirmation that lists what is lost", async () => {
  mockDeleteAccount.mockResolvedValue("deleted");
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByText("settings.delete"));
  await waitFor(() => expect(mockDeleteAccount).toHaveBeenCalled());
  expect(mockConfirm).toHaveBeenCalledWith(
    expect.objectContaining({ title: "delete.title", message: "delete.message", destructive: true }),
  );
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
});

it("closing the Apple sheet during delete shows no error and stays", async () => {
  mockDeleteAccount.mockResolvedValue("cancelled");
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByText("settings.delete"));
  await waitFor(() => expect(mockDeleteAccount).toHaveBeenCalled());
  expect(mockReplace).not.toHaveBeenCalled();
  expect(mockReportError).not.toHaveBeenCalled();
});

it("a failed delete says so", async () => {
  mockDeleteAccount.mockResolvedValue("failed");
  const view = await render(<DataControlsScreen />);
  await fireEvent.press(view.getByText("settings.delete"));
  await waitFor(() =>
    expect(mockReportError).toHaveBeenCalledWith(null, "settings.delete_failed"),
  );
  expect(mockReplace).not.toHaveBeenCalled();
});

it("shows the account deletion in progress", async () => {
  mockProgress = "deleting";
  const view = await render(<DataControlsScreen />);
  expect(view.getByText("settings.delete_progress")).toBeTruthy();
});

