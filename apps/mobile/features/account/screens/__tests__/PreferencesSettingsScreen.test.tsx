import { fireEvent, render } from "@testing-library/react-native";

import PreferencesSettingsScreen from "@/features/account/screens/PreferencesSettingsScreen";

const mockSetHaptics = jest.fn();
const mockUpdateUser = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({ Redirect: () => null, router: { push: jest.fn() } }));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "tok", user: { response_tone: "casual" }, updateUser: mockUpdateUser }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({ useActionFeedbackOptional: () => null }));
jest.mock("@/contexts/AppearanceContext", () => ({
  useHaptics: () => ({ enabled: true, setEnabled: mockSetHaptics }),
}));
jest.mock("@/features/account/components/SettingsFieldSheet", () => ({
  SettingsFieldSheet: () => null,
}));

beforeEach(() => jest.clearAllMocks());

it("turns haptics off on this device from Personalization", async () => {
  const { getByRole } = await render(<PreferencesSettingsScreen />);
  await fireEvent.press(getByRole("switch", { name: "settings.haptics" }));
  expect(mockSetHaptics).toHaveBeenCalledWith(false);
});
