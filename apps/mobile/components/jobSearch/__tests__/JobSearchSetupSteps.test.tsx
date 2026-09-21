import { fireEvent, render } from "@testing-library/react-native";

import { DeliveryStep } from "@/components/jobSearch/setup/DeliveryStep";
import { LocationStep } from "@/components/jobSearch/setup/LocationStep";
import { ProfileStep } from "@/components/jobSearch/setup/ProfileStep";
import { RolesSkillsStep } from "@/components/jobSearch/setup/RolesSkillsStep";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/hooks/useResolvedColorScheme", () => ({
  useResolvedColorScheme: () => "light",
}));
jest.mock("@/components/Icon", () => ({ Icon: () => null }));
jest.mock("@/components/jobSearch/LocationFields", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const { Pressable, Text } = jest.requireActual("react-native");
  return {
    LocationFields: ({
      onChange,
    }: {
      onChange: (value: { city: string; region: string; country: string }) => void;
    }) =>
      React.createElement(
        Pressable,
        {
          onPress: () =>
            onChange({ city: "Lisbon", region: "Lisbon", country: "Portugal" }),
        },
        React.createElement(Text, null, "change-location"),
      ),
  };
});
jest.mock("@/components/jobSearch/SearchableMultiSelect", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const { Pressable, Text } = jest.requireActual("react-native");
  return {
    SearchableMultiSelect: ({
      sheetTitle,
      onChange,
    }: {
      sheetTitle: string;
      onChange: (values: string[]) => void;
    }) =>
      React.createElement(
        Pressable,
        { onPress: () => onChange([`${sheetTitle}-choice`]) },
        React.createElement(Text, null, `${sheetTitle}-picker`),
      ),
  };
});

describe("job search setup steps", () => {
  it("controls location and work-mode values through callbacks", async () => {
    const onPlaceChange = jest.fn();
    const onWorkModePress = jest.fn();
    const screen = await render(
      <LocationStep
        place={{ city: "", region: "", country: "" }}
        workModes={["remote"]}
        busy={false}
        onPlaceChange={onPlaceChange}
        onWorkModePress={onWorkModePress}
      />,
    );

    await fireEvent.press(screen.getByText("change-location"));
    await fireEvent.press(screen.getByText("my_job.work_hybrid"));

    expect(onPlaceChange).toHaveBeenCalledWith({
      city: "Lisbon",
      region: "Lisbon",
      country: "Portugal",
    });
    expect(onWorkModePress).toHaveBeenCalledWith("hybrid");
  });

  it("routes role and skill selections and displays role validation", async () => {
    const onRolesChange = jest.fn();
    const onSkillsChange = jest.fn();
    const screen = await render(
      <RolesSkillsStep
        roles={[]}
        skills={[]}
        roleError
        busy={false}
        onRolesChange={onRolesChange}
        onSkillsChange={onSkillsChange}
      />,
    );

    expect(screen.getByText("my_job.role_required_body")).toBeTruthy();
    await fireEvent.press(screen.getByText("my_job.roles_label-picker"));
    await fireEvent.press(screen.getByText("my_job.skills_label-picker"));

    expect(onRolesChange).toHaveBeenCalledWith(["my_job.roles_label-choice"]);
    expect(onSkillsChange).toHaveBeenCalledWith(["my_job.skills_label-choice"]);
  });

  it("routes resume, experience, and salary controls", async () => {
    const onChooseResume = jest.fn();
    const onRemoveResume = jest.fn();
    const onExperiencePress = jest.fn();
    const onSalaryChange = jest.fn();
    const onSponsorshipChange = jest.fn();
    const onExcludedCompaniesChange = jest.fn();
    const screen = await render(
      <ProfileStep
        resumeName="resume.pdf"
        uploadingResume={false}
        levels={["entry"]}
        salary="100000"
        requiresSponsorship={null}
        excludedCompanies="Acme"
        salaryError
        busy={false}
        onChooseResume={onChooseResume}
        onRemoveResume={onRemoveResume}
        onExperiencePress={onExperiencePress}
        onSalaryChange={onSalaryChange}
        onSponsorshipChange={onSponsorshipChange}
        onExcludedCompaniesChange={onExcludedCompaniesChange}
      />,
    );

    await fireEvent.press(screen.getByText("resume.pdf"));
    await fireEvent.press(screen.getByText("my_job.resume_remove"));
    await fireEvent.press(screen.getByText("my_job.level_entry"));
    await fireEvent.press(screen.getByText("my_job.sponsorship_yes"));
    await fireEvent.changeText(screen.getByPlaceholderText("100000"), "120000");
    await fireEvent.changeText(
      screen.getByPlaceholderText("my_job.excluded_companies_placeholder"),
      "Acme, Contoso",
    );

    expect(onChooseResume).toHaveBeenCalledTimes(1);
    expect(onRemoveResume).toHaveBeenCalledTimes(1);
    expect(onExperiencePress).toHaveBeenCalledWith("entry");
    expect(onSponsorshipChange).toHaveBeenCalledWith(true);
    expect(onSalaryChange).toHaveBeenCalledWith("120000");
    expect(onExcludedCompaniesChange).toHaveBeenCalledWith("Acme, Contoso");
    expect(screen.getByText("my_job.salary_invalid_body")).toBeTruthy();
  });

  it("routes all delivery controls without owning their state", async () => {
    const onOpenCount = jest.fn();
    const onOpenFrequency = jest.fn();
    const onOpenDatePicker = jest.fn();
    const screen = await render(
      <DeliveryStep
        count={10}
        frequencyLabel="Weekdays"
        timeLabel="Tomorrow at 8:00 AM"
        isPro
        busy={false}
        summary={["Nurse", "Berlin"]}
        onOpenCount={onOpenCount}
        onOpenFrequency={onOpenFrequency}
        onOpenDatePicker={onOpenDatePicker}
      />,
    );

    await fireEvent.press(screen.getByText("10 my_job.count_jobs"));
    await fireEvent.press(screen.getByText("Weekdays"));
    await fireEvent.press(screen.getByText("Tomorrow at 8:00 AM"));

    expect(screen.getByText("Nurse")).toBeTruthy();
    expect(screen.getByText("Berlin")).toBeTruthy();

    expect(onOpenCount).toHaveBeenCalledTimes(1);
    expect(onOpenFrequency).toHaveBeenCalledTimes(1);
    expect(onOpenDatePicker).toHaveBeenCalledTimes(1);
  });
});
