import { fireEvent, render } from "@testing-library/react-native";

import MyJobScreen from "@/app/my-job";

const mockRefresh = jest.fn(async () => {});
let mockLoading = true;
let mockError = false;

jest.mock("expo-router", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  return {
    Redirect: () => null,
    useRouter: () => ({ push: jest.fn() }),
    useFocusEffect: (callback: () => void) => React.useEffect(callback, [callback]),
  };
});
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", user: { plan: "free" } }),
}));
jest.mock("@/hooks/useAccountViewOwner", () => ({
  useAccountViewOwner: () => ({ key: "owner", isCurrent: () => true }),
}));
jest.mock("@/hooks/useJobSearch", () => ({
  useJobSearch: () => ({
    dashboard: { profile: null, matches: [] },
    loading: mockLoading,
    busy: false,
    error: mockError,
    refresh: mockRefresh,
    setSearchStatus: jest.fn(),
    setMatchStatus: jest.fn(),
    remove: jest.fn(),
  }),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/lib/share", () => ({ presentShareSheet: jest.fn() }));
jest.mock("@/lib/haptics", () => ({
  notifyWarning: jest.fn(),
  selection: jest.fn(),
  tap: jest.fn(),
}));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/components/jobSearch/JobMatchCard", () => ({ JobMatchCard: () => null }));
jest.mock("@/components/jobSearch/SearchProfileFields", () => ({
  SearchProfileFields: () => null,
}));
jest.mock("@/components/SkeletonLoader", () => {
  const { Text } = jest.requireActual("react-native");
  return { SkeletonList: () => <Text>SkeletonList</Text> };
});
jest.mock("@/components/StateView", () => {
  const { Pressable, Text } = jest.requireActual("react-native");
  return {
    StateView: ({
      title,
      onRetry,
    }: {
      title?: string;
      onRetry?: () => void;
    }) => (
      <>
        <Text>{title}</Text>
        {onRetry ? (
          <Pressable onPress={onRetry}>
            <Text>Retry</Text>
          </Pressable>
        ) : null}
      </>
    ),
  };
});
jest.mock("@/components/jobSearch/JobSearchActionsSheet", () => ({
  JobSearchActionsSheet: () => null,
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockLoading = true;
  mockError = false;
});

test("shows a skeleton while the first dashboard request is pending", async () => {
  const screen = await render(<MyJobScreen />);
  expect(screen.getByText("SkeletonList")).toBeTruthy();
  expect(screen.queryByText("my_job.hero_title")).toBeNull();
});

test("shows retryable error before onboarding after first-load failure", async () => {
  mockLoading = false;
  mockError = true;
  const screen = await render(<MyJobScreen />);
  expect(screen.getByText("my_job.refresh_error")).toBeTruthy();
  expect(screen.queryByText("my_job.hero_title")).toBeNull();

  mockRefresh.mockClear();
  await fireEvent.press(screen.getByText("Retry"));
  expect(mockRefresh).toHaveBeenCalledWith();
});

test("shows onboarding only after a successful empty response", async () => {
  mockLoading = false;
  const screen = await render(<MyJobScreen />);
  expect(screen.getByText("my_job.hero_title")).toBeTruthy();
  expect(screen.queryByText("my_job.refresh_error")).toBeNull();
});
