import { Alert } from "react-native";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import type { JobSearchProfile } from "@/lib/api";

import { JobSearchSetupForm } from "@/features/job-search/components/JobSearchSetupForm";

const mockRunJobSearch = jest.fn();
const mockUser = { plan: "pro", job: "Registered Nurse", location: "Berlin" };

jest.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "token-a", user: mockUser }),
}));
jest.mock("@/lib/api", () => {
  return {
    api: { runJobSearch: (...args: unknown[]) => mockRunJobSearch(...args) },
  };
});
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/ui/icons/Icon", () => ({ Icon: () => null }));
jest.mock("@/features/job-search/components/LocationFields", () => ({
  EMPTY_PLACE: { city: "", region: "", country: "" },
  composePlace: () => "Berlin",
  parsePlace: () => ({ city: "Berlin", region: "", country: "Germany" }),
  LocationFields: () => null,
}));
jest.mock("@/features/job-search/components/SearchableMultiSelect", () => ({
  SearchableMultiSelect: () => null,
}));
jest.mock("@/ui/pickers/DateTimePickerDialog", () => ({
  DateTimePickerDialog: () => null,
}));
jest.mock("@/ui/overlay/Sheet", () => ({
  Sheet: ({ children }: { children: React.ReactNode }) => {
    const React = jest.requireActual<typeof import("react")>("react");
    const { View } = jest.requireActual("react-native");
    return React.createElement(View, null, children);
  },
}));

beforeEach(() => {
  jest.clearAllMocks();
  jest.spyOn(Alert, "alert").mockImplementation(() => {});
  mockRunJobSearch.mockResolvedValue({ queued: true });
});

afterEach(() => jest.restoreAllMocks());

async function reachPayStep(screen: Awaited<ReturnType<typeof render>>) {
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.next"));
}

test("keeps setup open when save returns false", async () => {
  const onClose = jest.fn();
  const onSave = jest.fn(async () => false);
  const screen = await render(
    <JobSearchSetupForm
      initial={null}
      busy={false}
      onClose={onClose}
      onSave={onSave}
    />,
  );
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("my_job.start_search"));

  await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
  expect(onClose).not.toHaveBeenCalled();
  expect(screen.getByText("my_job.start_search")).toBeTruthy();
});

test("moves through all setup steps and back without saving", async () => {
  const onSave = jest.fn(async () => true);
  const screen = await render(
    <JobSearchSetupForm
      initial={null}
      busy={false}
      onClose={jest.fn()}
      onSave={onSave}
    />,
  );

  expect(screen.getByText("my_job.step0_title")).toBeTruthy();
  await fireEvent.press(screen.getByText("common.next"));
  expect(screen.getByText("my_job.step1_title")).toBeTruthy();
  await fireEvent.press(screen.getByText("common.next"));
  expect(screen.getByText("my_job.step2_title")).toBeTruthy();
  await fireEvent.press(screen.getByText("common.next"));
  expect(screen.getByText("my_job.step3_title")).toBeTruthy();

  await fireEvent.press(screen.getByText("common.back"));

  expect(screen.getByText("my_job.step2_title")).toBeTruthy();
  expect(onSave).not.toHaveBeenCalled();
});

test("saves setup without starting an unrequested search", async () => {
  const onClose = jest.fn();
  const onSave = jest.fn(async () => true);
  const screen = await render(
    <JobSearchSetupForm
      initial={null}
      busy={false}
      onClose={onClose}
      onSave={onSave}
    />,
  );
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("my_job.start_search"));

  await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
  expect(mockRunJobSearch).not.toHaveBeenCalled();
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ result_count: 10, frequency: "weekdays", work_modes: ["remote", "hybrid", "onsite"], experience_levels: ["internship", "entry", "mid", "senior"] }));
  expect(onClose).toHaveBeenCalledTimes(1);
});


test("editing the simpler form retains hidden preferences and saves experience beside job titles", async () => {
  const initial: JobSearchProfile = {
    id: "profile", revision: 7, target_roles: ["Registered Nurse"], skills: ["Care"],
    location: "Berlin, Germany", country: "Germany",
    included_locations: [{ country: "Germany", city: "Berlin" }, { country: "France", city: "Paris" }],
    excluded_locations: [{ country: "Germany", city: "Munich" }],
    years_experience: 3, salary_currency: "EUR", salary_period: "month", salary_min: 4000,
    work_modes: ["onsite"], experience_levels: ["senior"], requires_sponsorship: true,
    excluded_companies: ["Acme"], background: "Existing background",
    next_run_at: new Date(Date.now() + 86400000).toISOString(), status: "paused",
    last_run_at: null, last_run_status: null, created_at: "2026-01-01", updated_at: "2026-01-01",
  };
  const onSave = jest.fn(async () => true);
  const screen = await render(<JobSearchSetupForm initial={initial} busy={false} onClose={jest.fn()} onSave={onSave} />);
  expect(screen.queryByText("my_job.additional_locations")).toBeNull();
  expect(screen.queryByText("my_job.excluded_locations")).toBeNull();
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.changeText(screen.getByLabelText("my_job.actual_experience"), "5.5");
  await fireEvent.press(screen.getByText("common.next"));
  expect(screen.queryByText("my_job.actual_experience")).toBeNull();
  expect(screen.queryByText("my_job.sponsorship_label")).toBeNull();
  expect(screen.queryByText("my_job.excluded_companies_label")).toBeNull();
  expect(screen.queryByText("my_job.salary_currency")).toBeNull();
  await fireEvent.changeText(screen.getByLabelText("my_job.salary_label"), "4500");
  await fireEvent.press(screen.getByText("common.next"));
  await fireEvent.press(screen.getByText("common.save"));
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
    expected_revision: 7, years_experience: 5.5, salary_min: 4500, salary_currency: "EUR", salary_period: "month",
    included_locations: [{ country: "Germany", region: "", city: "Berlin" }, { country: "France", city: "Paris" }],
    country: null, excluded_locations: initial.excluded_locations,
    requires_sponsorship: true, excluded_companies: ["Acme"], background: initial.background,
  }));
});

test("Minimum pay accepts only digits, including pasted text, using the visible country currency", async () => {
  const onSave = jest.fn(async () => true);
  const screen = await render(<JobSearchSetupForm initial={null} busy={false} onClose={jest.fn()} onSave={onSave} />);
  await reachPayStep(screen);
  expect(screen.queryByText("my_job.resume_label")).toBeNull();
  await fireEvent.changeText(screen.getByLabelText("my_job.salary_label"), "abc100,000USD");
  expect(screen.getByLabelText("my_job.salary_label").props.value).toBe("100000");
  expect(screen.getByLabelText("my_job.salary_label").props.keyboardType).toBe("number-pad");
  await fireEvent.press(screen.getByText("common.next"));
  expect(screen.queryByText("my_job.review_title")).toBeNull();
  await fireEvent.press(screen.getByText("my_job.start_search"));
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ salary_min: 100000, salary_currency: "EUR" }));
});
