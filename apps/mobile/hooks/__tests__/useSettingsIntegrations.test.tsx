import React from "react";
import { Alert, Text } from "react-native";
import { act, render } from "@testing-library/react-native";

jest.mock("expo-router", () => ({
  useFocusEffect: jest.fn(),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok" }),
}));

const mockInvalidateSuggested = jest.fn();
jest.mock("@/lib/cache/suggestedRemindersCache", () => ({
  invalidateSuggestedRemindersCache: () => mockInvalidateSuggested(),
}));

jest.mock("@/lib/cache/integrationStatusCache", () => ({
  patchIntegrationStatusCache: jest.fn(),
}));

jest.mock("@/lib/expoRuntime", () => ({
  isExpoGo: () => false,
}));

jest.mock("@/lib/google-calendar", () => ({
  connectGoogleCalendar: jest.fn(),
}));
jest.mock("@/lib/google-gmail", () => ({
  connectGoogleGmail: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  api: {
    googleCalendarStatus: jest.fn(),
    googleGmailStatus: jest.fn(),
    disconnectGoogleCalendar: jest.fn(),
    disconnectGoogleGmail: jest.fn(),
    connectGoogleCalendar: jest.fn(),
    connectGoogleGmail: jest.fn(),
    syncGoogleGmail: jest.fn(),
  },
}));

import { useSettingsIntegrations } from "@/hooks/useSettingsIntegrations";
import { api } from "@/lib/api";
import { patchIntegrationStatusCache } from "@/lib/cache/integrationStatusCache";

const mockApi = api as unknown as {
  googleCalendarStatus: jest.Mock;
  googleGmailStatus: jest.Mock;
  disconnectGoogleCalendar: jest.Mock;
};

let current: ReturnType<typeof useSettingsIntegrations>;

function Probe() {
  const result = useSettingsIntegrations();
  React.useLayoutEffect(() => {
    current = result;
  }, [result]);
  return <Text>{result.calendarStatus?.connected ? "on" : "off"}</Text>;
}

async function mount() {
  await act(async () => {
    render(<Probe />);
  });
  await act(async () => {
    await current.refresh();
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockApi.googleCalendarStatus.mockResolvedValue({
    connected: true,
    configured: true,
    email: "user@example.com",
  });
  mockApi.googleGmailStatus.mockResolvedValue({
    connected: true,
    configured: true,
    email: "user@example.com",
  });
  mockApi.disconnectGoogleCalendar.mockResolvedValue(undefined);
});

describe("useSettingsIntegrations disconnect", () => {
  it("warns about sibling drop and refreshes both statuses after calendar disconnect", async () => {
    let confirm: (() => void | Promise<void>) | undefined;
    const alertSpy = jest.spyOn(Alert, "alert").mockImplementation((_title, _msg, buttons) => {
      confirm = buttons?.find((b) => b.style === "destructive")?.onPress;
    });

    await mount();
    expect(current.gmailStatus?.connected).toBe(true);

    mockApi.googleCalendarStatus.mockResolvedValue({ connected: false, configured: true });
    mockApi.googleGmailStatus.mockResolvedValue({ connected: false, configured: true });

    await act(async () => {
      current.disconnectCalendar();
    });
    expect(Alert.alert).toHaveBeenCalledWith(
      "settings.calendar_title",
      "settings.calendar_disconnect_confirm",
      expect.any(Array),
    );

    await act(async () => {
      await confirm?.();
    });

    expect(mockApi.disconnectGoogleCalendar).toHaveBeenCalledWith("tok");
    expect(mockInvalidateSuggested).toHaveBeenCalled();
    expect(current.calendarStatus?.connected).toBe(false);
    expect(current.gmailStatus?.connected).toBe(false);
    expect(patchIntegrationStatusCache).toHaveBeenCalledWith({
      calendarConnected: false,
      gmailConnected: false,
    });

    alertSpy.mockRestore();
  });
});
