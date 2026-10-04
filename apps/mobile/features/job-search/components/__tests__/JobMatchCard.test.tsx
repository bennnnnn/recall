import { fireEvent, render } from "@testing-library/react-native";

import { JobMatchCard } from "@/features/job-search/components/JobMatchCard";
import type { JobMatch } from "@/lib/api";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const baseMatch: JobMatch = {
  id: "m1",
  title: "Backend Engineer",
  company: "Acme",
  company_logo_url: "https://cdn.acme.com/logo.png",
  location: "Berlin, Germany",
  work_mode: "remote",
  salary: "$90,000 - $120,000",
  experience: "3+ years",
  match_score: 87,
  match_kind: "qualifying",
  fit_label: "Strong fit",
  url: "https://jobs.example.com/roles/123",
  source: "jobs.example.com",
  posted_at: "2d ago",
  summary: "Build production APIs.",
  required_skills: ["Python", "FastAPI"],
  match_reasons: ["Python matches your skills", "Remote fits your preference"],
  gap: null,
  found_at: "2026-09-18T00:00:00Z",
  status: "new",
  is_saved: false,
  notes: null,
};

describe("JobMatchCard", () => {
  it("shows an evidence label and concise posting facts", async () => {
    const { getByLabelText, getByText, queryByLabelText } = await render(
      <JobMatchCard match={baseMatch} onStatus={jest.fn()} onSavedChange={jest.fn()} />,
    );
    expect(getByText("my_job.fit_strong")).toBeTruthy();
    expect(getByLabelText("my_job.meta_location: Berlin, Germany")).toBeTruthy();
    expect(getByLabelText("my_job.meta_work_mode: my_job.work_remote")).toBeTruthy();
    expect(getByLabelText("my_job.meta_salary: $90,000 - $120,000")).toBeTruthy();
    expect(queryByLabelText("my_job.meta_experience: 3+ years")).toBeNull();
    expect(queryByLabelText("my_job.meta_skills: Python, FastAPI")).toBeNull();
    expect(getByLabelText("my_job.meta_posted: 2d ago")).toBeTruthy();
  });

  it("shows one concrete fit reason on the card", async () => {
    const { getByText, queryByText } = await render(<JobMatchCard match={baseMatch} onStatus={jest.fn()} onSavedChange={jest.fn()} />);
    expect(getByText("Python matches your skills")).toBeTruthy();
    expect(queryByText("Remote fits your preference")).toBeNull();
  });

  it("shows the hiring-company logo and has no dismiss control", async () => {
    const { getByTestId, queryByLabelText } = await render(
      <JobMatchCard match={baseMatch} onStatus={jest.fn()} onSavedChange={jest.fn()} />,
    );
    expect(getByTestId("company-logo-image").props.source).toEqual({
      uri: "https://cdn.acme.com/logo.png",
    });
    expect(queryByLabelText("my_job.not_interested")).toBeNull();
  });

  it("keeps full descriptions on the detail screen", async () => {
    const { queryByText } = await render(
      <JobMatchCard match={baseMatch} onStatus={jest.fn()} onSavedChange={jest.fn()} />,
    );
    expect(queryByText("Build production APIs.")).toBeNull();
  });

  it("falls back to the company initial when there is no logo", async () => {
    const { getByText, queryByText } = await render(
      <JobMatchCard
        match={{ ...baseMatch, company_logo_url: null, match_score: null }}
        onStatus={jest.fn()}
        onSavedChange={jest.fn()}
      />,
    );
    expect(getByText("A")).toBeTruthy();
    expect(queryByText(/%$/)).toBeNull();
  });

  it("omits chips for missing fields", async () => {
    const { queryByText } = await render(
      <JobMatchCard
        match={{ ...baseMatch, salary: null, experience: null, location: null }}
        onStatus={jest.fn()}
        onSavedChange={jest.fn()}
      />,
    );
    expect(queryByText("Berlin, Germany")).toBeNull();
    expect(queryByText("3+ years")).toBeNull();
    expect(queryByText("$90,000 - $120,000")).toBeNull();
  });

  it("shows a stage badge for interviewing/offer/rejected only", async () => {
    const { getByText, rerender, queryByText } = await render(
      <JobMatchCard
        match={{ ...baseMatch, status: "interviewing" }}
        onStatus={jest.fn()}
        onSavedChange={jest.fn()}
      />,
    );
    expect(getByText("my_job.stage_interviewing")).toBeTruthy();
    await rerender(
      <JobMatchCard
        match={{ ...baseMatch, status: "new" }}
        onStatus={jest.fn()}
        onSavedChange={jest.fn()}
      />,
    );
    expect(queryByText("my_job.stage_interviewing")).toBeNull();
  });

  it("bookmarks an applied job without changing its application stage", async () => {
    const onStatus = jest.fn();
    const onSavedChange = jest.fn();
    const { getByText } = await render(
      <JobMatchCard
        match={{ ...baseMatch, status: "applied", is_saved: false }}
        onStatus={onStatus}
        onSavedChange={onSavedChange}
      />,
    );

    await fireEvent.press(getByText("my_job.save"));

    expect(onSavedChange).toHaveBeenCalledWith(true);
    expect(onStatus).not.toHaveBeenCalled();
  });

  it("keeps later pipeline stages visibly applied and prevents accidental regression", async () => {
    const onStatus = jest.fn();
    const { getByRole } = await render(
      <JobMatchCard
        match={{ ...baseMatch, status: "offer" }}
        onStatus={onStatus}
        onSavedChange={jest.fn()}
      />,
    );
    const applied = getByRole("button", { name: "my_job.applied" });

    expect(applied.props.accessibilityState).toEqual({ selected: true, disabled: true });
    await fireEvent.press(applied);
    expect(onStatus).not.toHaveBeenCalled();
  });

  it("keeps the external job action compact instead of stretching across the card", async () => {
    const { getByRole } = await render(
      <JobMatchCard match={baseMatch} onStatus={jest.fn()} onSavedChange={jest.fn()} />,
    );

    expect(getByRole("button", { name: "my_job.view_job" })).not.toHaveStyle({
      flexGrow: 1,
    });
  });
});
