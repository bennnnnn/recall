import { fireEvent, render } from "@testing-library/react-native";

import MyJobSetupScreen from "@/app/my-job/setup";

const mockRefresh = jest.fn(async () => {});
let mockLoading = true;
let mockError = false;

jest.mock("expo-router", () => ({
  Redirect: () => null,
  useRouter: () => ({ back: jest.fn() }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a" }),
}));
jest.mock("@/hooks/useAccountViewOwner", () => ({
  useAccountViewOwner: () => ({ key: "owner", isCurrent: () => true }),
}));
jest.mock("@/features/job-search/hooks/useJobSearch", () => ({
  useJobSearch: () => ({
    dashboard: { profile: null, matches: [] },
    loading: mockLoading,
    busy: false,
    error: mockError,
    refresh: mockRefresh,
    save: jest.fn(),
  }),
}));
jest.mock("@/features/job-search/components/JobSearchSetupForm", () => {
  const { Text } = jest.requireActual("react-native");
  return { JobSearchSetupForm: () => <Text>SetupForm</Text> };
});
jest.mock("@/components/SkeletonLoader", () => {
  const { Text } = jest.requireActual("react-native");
  return { SkeletonList: () => <Text>SkeletonList</Text> };
});
jest.mock("@/components/StateView", () => {
  const { Pressable, Text } = jest.requireActual("react-native");
  return {
    StateView: ({ title, onRetry }: { title?: string; onRetry?: () => void }) => (
      <>
        <Text>{title}</Text>
        <Pressable onPress={onRetry}>
          <Text>Retry</Text>
        </Pressable>
      </>
    ),
  };
});

beforeEach(() => {
  jest.clearAllMocks();
  mockLoading = true;
  mockError = false;
});

test("shows a skeleton instead of the form during initial load", async () => {
  const screen = await render(<MyJobSetupScreen />);
  expect(screen.getByText("SkeletonList")).toBeTruthy();
  expect(screen.queryByText("SetupForm")).toBeNull();
});

test("shows retryable error instead of the form after first-load failure", async () => {
  mockLoading = false;
  mockError = true;
  const screen = await render(<MyJobSetupScreen />);
  expect(screen.getByText("my_job.refresh_error")).toBeTruthy();
  expect(screen.queryByText("SetupForm")).toBeNull();

  await fireEvent.press(screen.getByText("Retry"));
  expect(mockRefresh).toHaveBeenCalledWith();
});

test("shows the form only after a successful empty response", async () => {
  mockLoading = false;
  const screen = await render(<MyJobSetupScreen />);
  expect(screen.getByText("SetupForm")).toBeTruthy();
  expect(screen.queryByText("my_job.refresh_error")).toBeNull();
});
