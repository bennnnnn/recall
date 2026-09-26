import { act, fireEvent, render, within } from "@testing-library/react-native";

import MyJobScreen from "@/app/my-job";
import type { JobMatch, JobSearchDashboard, JobSearchProfile } from "@/lib/api";

const mockRefresh = jest.fn(async () => {});
const mockRunNow = jest.fn(async () => true);
let mockLoading = true;
let mockError = false;
let mockDashboard: JobSearchDashboard = { profile: null, matches: [] };

jest.mock("expo-router", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  return {
    Redirect: () => null,
    useRouter: () => ({ push: jest.fn() }),
    useFocusEffect: (callback: () => void) =>
      React.useEffect(callback, [callback]),
  };
});
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", user: { plan: "free" } }),
}));
jest.mock("@/hooks/useAccountViewOwner", () => ({
  useAccountViewOwner: () => ({ key: "owner", isCurrent: () => true }),
}));
jest.mock("@/features/job-search/hooks/useJobSearch", () => ({
  useJobSearch: () => ({
    dashboard: mockDashboard,
    loading: mockLoading,
    busy: false,
    error: mockError,
    refresh: mockRefresh,
    setSearchStatus: jest.fn(),
    setMatchStatus: jest.fn(),
    setMatchSaved: jest.fn(),
    runNow: mockRunNow,
    remove: jest.fn(),
  }),
}));
jest.mock("@shopify/flash-list");
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
const mockPresentShare = jest.fn(async () => undefined);
jest.mock("@/lib/share", () => ({
  presentShareSheet: (...args: unknown[]) => mockPresentShare(...(args as [])),
}));
jest.mock("@/lib/haptics", () => ({
  notifyWarning: jest.fn(),
  selection: jest.fn(),
  tap: jest.fn(),
}));
jest.mock("@/ui/icons/Icon", () => ({ Icon: () => null }));
jest.mock("@/features/job-search/components/JobMatchCard", () => {
  const { Text } = jest.requireActual("react-native");
  return {
    JobMatchCard: ({ match }: { match: JobMatch }) => (
      <Text>{match.title}</Text>
    ),
  };
});
jest.mock("@/features/job-search/components/SearchProfileFields", () => ({
  SearchProfileFields: () => null,
}));
jest.mock("@/ui/feedback/SkeletonLoader", () => {
  const { Text } = jest.requireActual("react-native");
  return { SkeletonList: () => <Text>SkeletonList</Text> };
});
jest.mock("@/ui/feedback/StateView", () => {
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
let mockMenu: { onShare: () => void; visible: boolean };
jest.mock("@/features/job-search/components/JobSearchActionsMenu", () => ({
  JobSearchActionsMenu: (props: typeof mockMenu) => {
    mockMenu = props;
    return null;
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockLoading = true;
  mockError = false;
  mockDashboard = { profile: null, matches: [] };
});

function profile(): JobSearchProfile {
  return {
    id: "profile-a",
    target_roles: ["Registered Nurse"],
    skills: [],
    location: "Berlin",
    work_modes: ["onsite"],
    experience_levels: ["mid"],
    salary_min: null,
    requires_sponsorship: null,
    excluded_companies: [],
    background: null,
    resume_attachment_id: null,
    resume_filename: null,
    result_count: 5,
    frequency: "weekly",
    next_run_at: "2026-09-20T08:00:00.000Z",
    status: "active",
    last_run_at: null,
    last_run_status: null,
    created_at: "2026-09-18T00:00:00.000Z",
    updated_at: "2026-09-18T00:00:00.000Z",
  };
}

function match(id: string, status: JobMatch["status"], isSaved = false): JobMatch {
  return {
    id,
    title: `Job ${id}`,
    company: "Acme",
    company_logo_url: null,
    location: null,
    work_mode: null,
    salary: null,
    experience: null,
    match_score: 80,
    url: `https://jobs.example.com/${id}`,
    source: "jobs.example.com",
    posted_at: null,
    summary: null,
    required_skills: [],
    match_reasons: [],
    gap: null,
    found_at: "2026-09-18T00:00:00.000Z",
    status,
    is_saved: isSaved,
    notes: null,
  };
}

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
  expect(screen.getByRole("button", { name: "my_job.setup_cta" })).toBeTruthy();
});

test("uses a minimum 44 point menu target", async () => {
  mockLoading = false;
  mockDashboard = { profile: profile(), matches: [] };
  const screen = await render(<MyJobScreen />);
  expect(screen.getByLabelText("my_job.menu_a11y")).toHaveStyle({
    width: 44,
    height: 44,
  });
});

test("shows application pipeline lists and filters each stage", async () => {
  mockLoading = false;
  mockDashboard = {
    profile: profile(),
    matches: [
      match("new", "new"),
      match("applied", "applied"),
      match("interview", "interviewing"),
      match("offer", "offer"),
      match("rejected", "rejected"),
    ],
  };
  const screen = await render(<MyJobScreen />);

  expect(screen.getByText("Job new")).toBeTruthy();
  expect(screen.getByText("my_job.pipeline")).toBeTruthy();

  await fireEvent.press(
    screen.getByRole("button", {
      name: "my_job.pipeline: my_job.tab_all_stages",
    }),
  );
  expect(
    screen.getByRole("radio", { name: "my_job.tab_all_stages" }),
  ).toBeTruthy();
  await fireEvent.press(
    screen.getByRole("radio", { name: "my_job.tab_interviewing" }),
  );
  expect(screen.getByText("Job interview")).toBeTruthy();
  expect(screen.getByText("my_job.tab_interviewing")).toBeTruthy();
  expect(screen.queryByText("Job new")).toBeNull();

  await fireEvent.press(
    screen.getByRole("button", {
      name: "my_job.pipeline: my_job.tab_interviewing",
    }),
  );
  await fireEvent.press(
    screen.getByRole("radio", { name: "my_job.tab_offers" }),
  );
  expect(screen.getByText("Job offer")).toBeTruthy();
  expect(screen.getByText("my_job.tab_offers")).toBeTruthy();

  await fireEvent.press(
    screen.getByRole("button", {
      name: "my_job.pipeline: my_job.tab_offers",
    }),
  );
  await fireEvent.press(
    screen.getByRole("radio", { name: "my_job.tab_rejected" }),
  );
  expect(screen.getByText("Job rejected")).toBeTruthy();
  expect(screen.getByText("my_job.tab_rejected")).toBeTruthy();

  await fireEvent.press(
    screen.getByRole("button", {
      name: "my_job.pipeline: my_job.tab_rejected",
    }),
  );
  await fireEvent.press(
    screen.getByRole("radio", { name: "my_job.tab_applied" }),
  );
  expect(screen.getByText("Job applied")).toBeTruthy();
  expect(screen.getByText("my_job.tab_applied")).toBeTruthy();
});

test("keeps a bookmarked applied job in Saved and Applied", async () => {
  mockLoading = false;
  mockDashboard = {
    profile: profile(),
    matches: [match("applied-saved", "applied", true)],
  };
  const screen = await render(<MyJobScreen />);

  expect(screen.queryByText("Job applied-saved")).toBeNull();
  await fireEvent.press(screen.getByRole("tab", { name: /my_job\.tab_saved/ }));
  expect(screen.getByText("Job applied-saved")).toBeTruthy();

  await fireEvent.press(
    screen.getByRole("button", { name: "my_job.pipeline: my_job.tab_all_stages" }),
  );
  await fireEvent.press(screen.getByRole("radio", { name: "my_job.tab_applied" }));
  expect(screen.getByText("Job applied-saved")).toBeTruthy();
});

test("shows a retry action when the last search failed", async () => {
  mockLoading = false;
  mockDashboard = {
    profile: profile(),
    matches: [],
  };
  mockDashboard.profile!.last_run_status = "error";
  const screen = await render(<MyJobScreen />);

  expect(screen.getByText("my_job.run_failed_title")).toBeTruthy();
  await fireEvent.press(screen.getByText("common.retry"));
  expect(mockRunNow).toHaveBeenCalledTimes(1);
});

test("shares the search from the share sheet", async () => {
  mockLoading = false;
  mockDashboard = { profile: profile(), matches: [] };
  const screen = await render(<MyJobScreen />);
  const hidden = { includeHiddenElements: true };
  expect(screen.queryByText("share.search_heading", hidden)).toBeNull();

  await act(async () => mockMenu.onShare());
  expect(mockMenu.visible).toBe(false);
  expect(screen.getByText("share.search_heading", hidden)).toBeTruthy();
  const sheet = within(screen.getByTestId("job-search-share-sheet", hidden));
  expect(sheet.getByText("Registered Nurse", hidden)).toBeTruthy();
  expect(sheet.queryByTestId("job-search-share-sheet-pdf", hidden)).toBeNull();

  await act(async () => {
    fireEvent(screen.getByTestId("app-sheet-modal", hidden), "show");
  });
  expect(mockPresentShare).toHaveBeenCalledWith({
    message: "Registered Nurse\nBerlin · onsite\nmy_job.cadence_weekly",
    title: "my_job.title",
  });
});
