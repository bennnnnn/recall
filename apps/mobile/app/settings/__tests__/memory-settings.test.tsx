import { render } from "@testing-library/react-native";

import MemorySettingsScreen from "@/app/settings/memory-settings";

jest.mock("@expo/vector-icons", () => ({ Ionicons: "Ionicons" }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => ({ push: jest.fn() }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    token: "tok",
    user: { memory_enabled: true },
  }),
}));
jest.mock("@/hooks/useAccountViewOwner", () => ({
  useAccountViewOwner: () => ({ key: "1", isCurrent: () => true }),
}));
jest.mock("@/hooks/useMemoryToggle", () => ({
  useMemoryToggle: () => ({ saving: false, toggle: jest.fn() }),
}));
jest.mock("@/contexts/actionFeedbackCore", () => ({
  useActionFeedbackOptional: () => null,
}));
jest.mock("@/lib/cache/memoryListCache", () => ({
  prefetchMemories: jest.fn(),
  invalidateMemoriesCache: jest.fn(),
}));
jest.mock("@/lib/api", () => ({
  api: { clearMemories: jest.fn() },
}));

describe("memory settings", () => {
  it("shows Manage instead of a saved count", async () => {
    const { getByText, queryByText } = await render(<MemorySettingsScreen />);
    expect(getByText("settings.memory_manage")).toBeTruthy();
    expect(queryByText("settings.memory_count")).toBeNull();
    expect(getByText("settings.memory_clear_all")).toBeTruthy();
  });
});
