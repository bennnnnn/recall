import { fireEvent, render, waitFor } from "@testing-library/react-native";

import JobMatchDetailScreen from "@/app/my-job/match/[id]";
import type { JobMatch } from "@/lib/api";
import { cacheJobMatches, clearJobMatchCache } from "@/lib/jobSearch/matchCache";

let mockId = "m1";
let mockPlan: "free" | "pro" = "free";
const mockBack = jest.fn();
const mockGetJobSearch = jest.fn();
const mockSetJobMatchStatus = jest.fn(async () => ({ profile: null, matches: [] }));
const mockSetJobMatchSaved = jest.fn(async () => ({ profile: null, matches: [] }));
const mockGenerateCoverLetter = jest.fn(async () => ({ cover_letter: "Dear team, ..." }));

jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ id: mockId }),
  useRouter: () => ({ back: mockBack, push: jest.fn() }),
}));
jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", user: { id: "user", plan: mockPlan } }),
}));
jest.mock("@/hooks/useAccountViewOwner", () => ({
  useAccountViewOwner: () => ({ key: "owner", isCurrent: () => true }),
}));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-clipboard", () => ({ setStringAsync: jest.fn(async () => {}) }));
jest.mock("@/lib/share", () => ({ presentShareSheet: jest.fn(async () => ({})) }));
jest.mock("@/lib/haptics", () => ({
  tap: jest.fn(),
  selection: jest.fn(),
  notifyWarning: jest.fn(),
}));
jest.mock("@/lib/api", () => ({
  api: {
    getJobSearch: (...args: unknown[]) => mockGetJobSearch(...args),
    setJobMatchStatus: (...args: unknown[]) => mockSetJobMatchStatus(...args),
    setJobMatchSaved: (...args: unknown[]) => mockSetJobMatchSaved(...args),
    generateCoverLetter: (...args: unknown[]) => mockGenerateCoverLetter(...args),
  },
}));

function match(overrides: Partial<JobMatch> = {}): JobMatch {
  return {
    id: "m1",
    title: "Registered Nurse",
    company: "Acme Health",
    company_logo_url: "https://cdn.acme.test/logo.png",
    location: "Berlin, Germany",
    work_mode: "onsite",
    salary: "€60,000+",
    experience: "3+ years",
    match_score: 88,
    posted_at: "2d ago",
    summary: "Full summary of the role.",
    required_skills: ["ACLS", "Triage"],
    match_reasons: ["ICU experience", "German license", "Shift fit"],
    gap: "No pediatric experience",
    url: "https://jobs.example.com/1",
    source: "jobs.example.com",
    status: "new",
    is_saved: false,
    notes: null,
    found_at: "2026-09-18T00:00:00Z",
    ...overrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

afterEach(() => {
  clearJobMatchCache();
  mockPlan = "free";
  jest.clearAllMocks();
});

test("renders the cached match instantly with scan-first details", async () => {
  cacheJobMatches("user", [match()]);
  const { getByLabelText, getByText, getAllByText, queryByText } = await render(
    <JobMatchDetailScreen />,
  );
  expect(getByText("Registered Nurse")).toBeTruthy();
  // Company shows in the header and under the title.
  expect(getAllByText("Acme Health").length).toBeGreaterThan(0);
  expect(getByText("88%")).toBeTruthy();
  expect(getByLabelText("my_job.meta_skills: ACLS, Triage")).toBeTruthy();
  expect(queryByText("Full summary of the role.")).toBeNull();
  expect(queryByText("my_job.not_interested")).toBeNull();
  expect(queryByText("Shift fit")).toBeNull();
  await fireEvent.press(getByLabelText("my_job.why_matches"));
  // All reasons render after expansion (the card truncates to three).
  expect(getByText("Shift fit")).toBeTruthy();
  expect(getByText("No pediatric experience")).toBeTruthy();
  expect(getByText(/jobs\.example\.com/)).toBeTruthy();
  expect(queryByText("my_job.detail_not_found")).toBeNull();
  expect(mockGetJobSearch).not.toHaveBeenCalled();
});

test("shows the structured skeleton during a cold load", async () => {
  const pending = deferred<{ profile: null; matches: JobMatch[] }>();
  mockGetJobSearch.mockReturnValue(pending.promise);
  const screen = await render(<JobMatchDetailScreen />);
  expect(screen.getByTestId("job-match-detail-skeleton")).toBeTruthy();

  pending.resolve({ profile: null, matches: [match()] });
  await waitFor(() => expect(screen.getByText("Registered Nurse")).toBeTruthy());
});

test("cold start fetches the dashboard and shows a missing-match state", async () => {
  mockGetJobSearch.mockResolvedValue({ profile: null, matches: [match({ id: "other" })] });
  const { getByText } = await render(<JobMatchDetailScreen />);
  await waitFor(() => expect(getByText("my_job.detail_not_found")).toBeTruthy());
  expect(mockGetJobSearch).toHaveBeenCalledWith("token-a");
});

test("cold-load failure shows Retry instead of not-found and can recover", async () => {
  mockGetJobSearch
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ profile: null, matches: [match()] });
  const { getByText, queryByText } = await render(<JobMatchDetailScreen />);
  await waitFor(() => expect(getByText("my_job.refresh_error")).toBeTruthy());
  expect(queryByText("my_job.detail_not_found")).toBeNull();

  await fireEvent.press(getByText("common.retry"));
  await waitFor(() => expect(getByText("Registered Nurse")).toBeTruthy());
  expect(mockGetJobSearch).toHaveBeenCalledTimes(2);
});

test("cold start renders a fetched match", async () => {
  mockGetJobSearch.mockResolvedValue({ profile: null, matches: [match()] });
  const { getByText } = await render(<JobMatchDetailScreen />);
  await waitFor(() => expect(getByText("Registered Nurse")).toBeTruthy());
});

test("stage picker updates the match status", async () => {
  cacheJobMatches("user", [match()]);
  const { getAllByText, getByText } = await render(<JobMatchDetailScreen />);
  // The stage row and the sheet title share the label — the row is first.
  await fireEvent.press(getAllByText("my_job.stage_label")[0]);
  await fireEvent.press(getByText("my_job.stage_interviewing"));
  await waitFor(() =>
    expect(mockSetJobMatchStatus).toHaveBeenCalledWith("token-a", "m1", "interviewing", undefined),
  );
});

test("notes save on blur", async () => {
  cacheJobMatches("user", [match()]);
  const { getByPlaceholderText } = await render(<JobMatchDetailScreen />);
  const input = getByPlaceholderText("my_job.notes_placeholder");
  await fireEvent.changeText(input, "Call recruiter Friday");
  await fireEvent(input, "blur");
  await waitFor(() =>
    expect(mockSetJobMatchStatus).toHaveBeenCalledWith(
      "token-a",
      "m1",
      "new",
      "Call recruiter Friday",
    ),
  );
});

test("cover letter CTA is Pro-only and generates into the sheet", async () => {
  cacheJobMatches("user", [match()]);
  const { queryByText, rerender, getByText } = await render(<JobMatchDetailScreen />);
  expect(queryByText("my_job.cover_letter_cta")).toBeNull();

  mockPlan = "pro";
  await rerender(<JobMatchDetailScreen />);
  await fireEvent.press(getByText("my_job.cover_letter_cta"));
  await waitFor(() =>
    expect(mockGenerateCoverLetter).toHaveBeenCalledWith("token-a", "m1"),
  );
  await waitFor(() => expect(getByText("Dear team, ...")).toBeTruthy());
});

test("keeps notes usable above the keyboard", async () => {
  cacheJobMatches("user", [match()]);
  const screen = await render(<JobMatchDetailScreen />);
  expect(screen.getByTestId("job-match-detail-keyboard-view")).toBeTruthy();
  expect(screen.getByTestId("job-match-detail-scroll").props.keyboardShouldPersistTaps).toBe(
    "handled",
  );
});
