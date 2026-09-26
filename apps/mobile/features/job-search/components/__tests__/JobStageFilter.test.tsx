import { fireEvent, render } from "@testing-library/react-native";

import { JobStageFilter } from "@/features/job-search/components/JobStageFilter";

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));
jest.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

const counts = { all: 7, applied: 3, interviewing: 1, offer: 0, rejected: 3 };

describe("JobStageFilter", () => {
  it("opens the stage choices as a popover with the current one checked", async () => {
    const onOpen = jest.fn();
    const view = await render(
      <JobStageFilter value="applied" counts={counts} active onOpen={onOpen} onChange={jest.fn()} />,
    );
    await fireEvent.press(view.getByRole("button", { name: "my_job.pipeline: my_job.tab_applied" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(view.getByRole("radio", { name: "my_job.tab_applied" }).props.accessibilityState.checked).toBe(true);
    expect(view.getByRole("radio", { name: "my_job.tab_offers" }).props.accessibilityState.checked).toBe(false);
  });

  it("changes the filter and closes", async () => {
    const onChange = jest.fn();
    const view = await render(
      <JobStageFilter value="all" counts={counts} active={false} onOpen={jest.fn()} onChange={onChange} />,
    );
    await fireEvent.press(view.getByRole("button", { name: "my_job.pipeline: my_job.tab_all_stages" }));
    await fireEvent.press(view.getByRole("radio", { name: "my_job.tab_interviewing" }));
    expect(onChange).toHaveBeenCalledWith("interviewing");
    expect(view.queryByRole("radio", { name: "my_job.tab_interviewing" })).toBeNull();
  });
});
