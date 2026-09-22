import { fireEvent, render } from "@testing-library/react-native";

import { JobMatchCard } from "@/components/jobSearch/JobMatchCard";
import type { JobMatch } from "@/lib/api";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

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
  it("shows the fit score and all high-signal posting facts as chips", async () => {
    const { getByText } = await render(
      <JobMatchCard match={baseMatch} onStatus={jest.fn()} onSavedChange={jest.fn()} />,
    );
    expect(getByText("87%")).toBeTruthy();
    expect(getByText("Berlin, Germany")).toBeTruthy();
    expect(getByText("my_job.work_remote")).toBeTruthy();
    expect(getByText("$90,000 - $120,000")).toBeTruthy();
    expect(getByText("3+ years")).toBeTruthy();
    expect(getByText("Python")).toBeTruthy();
    expect(getByText("FastAPI")).toBeTruthy();
    expect(getByText("2d ago")).toBeTruthy();
  });

  it("keeps fit reasons folded until the user expands them", async () => {
    const { getByLabelText, getByText, queryByText } = await render(
      <JobMatchCard match={baseMatch} onStatus={jest.fn()} onSavedChange={jest.fn()} />,
    );
    expect(queryByText("Python matches your skills")).toBeNull();
    await fireEvent.press(getByLabelText("my_job.why_matches"));
    expect(getByText("Python matches your skills")).toBeTruthy();
    expect(getByText("Remote fits your preference")).toBeTruthy();
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

  it("does not render the summary body paragraph", async () => {
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
});
