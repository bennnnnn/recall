import { render, waitFor } from "@testing-library/react-native";

import JobMatchDetailScreen from "@/app/my-job/match/[id]";
import type { JobMatch } from "@/lib/api";
import { cacheJobMatches, clearJobMatchCache } from "@/lib/jobSearch/matchCache";

let mockId = "m1";
const mockBack = jest.fn();
const mockGetJobSearch = jest.fn();

jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ id: mockId }),
  useRouter: () => ({ back: mockBack, push: jest.fn() }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", user: { id: "user" } }),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  selection: jest.fn(),
  notifyWarning: jest.fn(),
}));
jest.mock("@/lib/api", () => ({
  api: {
    getJobSearch: (...args: unknown[]) => mockGetJobSearch(...args),
    setJobMatchStatus: jest.fn(async () => ({ profile: null, matches: [] })),
  },
}));

function match(overrides: Partial<JobMatch> = {}): JobMatch {
  return {
    id: "m1",
    title: "Registered Nurse",
    company: "Acme Health",
    location: "Berlin, Germany",
    work_mode: "onsite",
    salary: "€60,000+",
    experience: "3+ years",
    match_score: 88,
    posted_at: "2d ago",
    summary: "Full summary of the role.",
    match_reasons: ["ICU experience", "German license", "Shift fit"],
    gap: "No pediatric experience",
    url: "https://jobs.example.com/1",
    source: "jobs.example.com",
    status: "new",
    found_at: "2026-09-18T00:00:00Z",
    ...overrides,
  };
}

afterEach(() => {
  clearJobMatchCache();
  jest.clearAllMocks();
});

test("renders the cached match instantly without fetching", async () => {
  cacheJobMatches([match()]);
  const { getByText, getAllByText, queryByText } = await render(<JobMatchDetailScreen />);
  expect(getByText("Registered Nurse")).toBeTruthy();
  // Company shows in the header and under the title.
  expect(getAllByText("Acme Health").length).toBeGreaterThan(0);
  expect(getByText("88%")).toBeTruthy();
  expect(getByText("Full summary of the role.")).toBeTruthy();
  // All reasons render (the card truncates to three; detail shows all).
  expect(getByText("Shift fit")).toBeTruthy();
  expect(getByText("No pediatric experience")).toBeTruthy();
  expect(getByText(/jobs\.example\.com/)).toBeTruthy();
  expect(queryByText("my_job.detail_not_found")).toBeNull();
  expect(mockGetJobSearch).not.toHaveBeenCalled();
});

test("cold start fetches the dashboard and shows a missing-match state", async () => {
  mockGetJobSearch.mockResolvedValue({ profile: null, matches: [match({ id: "other" })] });
  const { getByText } = await render(<JobMatchDetailScreen />);
  await waitFor(() => expect(getByText("my_job.detail_not_found")).toBeTruthy());
  expect(mockGetJobSearch).toHaveBeenCalledWith("token-a");
});

test("cold start renders a fetched match", async () => {
  mockGetJobSearch.mockResolvedValue({ profile: null, matches: [match()] });
  const { getByText } = await render(<JobMatchDetailScreen />);
  await waitFor(() => expect(getByText("Registered Nurse")).toBeTruthy());
});
