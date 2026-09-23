import { fireEvent, render } from "@testing-library/react-native";

import { SearchableMultiSelect } from "@/features/job-search/components/SearchableMultiSelect";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

jest.mock("@/lib/reduceMotion", () => ({
  useReduceMotion: () => false,
}));

jest.mock("@shopify/flash-list", () => ({
  FlashList: ({
    data,
    renderItem,
    ListFooterComponent,
  }: {
    data: string[];
    renderItem: (args: { item: string }) => React.ReactNode;
    ListFooterComponent?: React.ReactNode;
  }) => {
    const React = jest.requireActual<typeof import("react")>("react");
    return React.createElement(
      React.Fragment,
      null,
      ...data.map((item) =>
        React.createElement(React.Fragment, { key: item }, renderItem({ item })),
      ),
      ListFooterComponent ?? null,
    );
  },
}));

const OPTIONS = ["Chef", "Sous Chef", "Pastry Chef", "Nurse", "Teacher"];

const baseProps = {
  values: [] as string[],
  onChange: jest.fn(),
  options: OPTIONS,
  placeholder: "Select job titles",
  sheetTitle: "Job titles",
  searchPlaceholder: "Search job titles",
  maxSelections: 3,
};

describe("SearchableMultiSelect", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("opens the sheet with the FULL list — not a short chip row", async () => {
    const { getByText, queryByText } = await render(<SearchableMultiSelect {...baseProps} />);

    expect(queryByText("Sous Chef")).toBeNull();
    await fireEvent.press(getByText("Select job titles"));

    for (const option of OPTIONS) {
      expect(getByText(option)).toBeTruthy();
    }
  });

  it("filters the long list as the user types", async () => {
    const { getByText, getByPlaceholderText, queryByText } = await render(
      <SearchableMultiSelect {...baseProps} />,
    );

    await fireEvent.press(getByText("Select job titles"));
    await fireEvent.changeText(getByPlaceholderText("Search job titles"), "sous");

    expect(getByText("Sous Chef")).toBeTruthy();
    expect(queryByText("Nurse")).toBeNull();
  });

  it("adds a tapped option and hides it from the list", async () => {
    const view = await render(<SearchableMultiSelect {...baseProps} />);

    await fireEvent.press(view.getByText("Select job titles"));
    await fireEvent.press(view.getByText("Chef"));

    expect(baseProps.onChange).toHaveBeenCalledWith(["Chef"]);

    // Controlled component: apply the new value, then the list drops it —
    // the only "Chef" left on screen is the selected chip.
    view.rerender(<SearchableMultiSelect {...baseProps} values={["Chef"]} />);
    expect(view.getAllByText("Chef")).toHaveLength(1);
  });

  it("never offers junk custom input like bb", async () => {
    const { getByText, getByPlaceholderText, queryByText } = await render(
      <SearchableMultiSelect {...baseProps} />,
    );

    await fireEvent.press(getByText("Select job titles"));
    await fireEvent.changeText(getByPlaceholderText("Search job titles"), "bb");

    expect(queryByText(/role_add_custom/)).toBeNull();
    expect(baseProps.onChange).not.toHaveBeenCalled();
  });

  it("offers an add-custom row for real entries not in the list", async () => {
    const { getByText, getByPlaceholderText } = await render(
      <SearchableMultiSelect {...baseProps} />,
    );

    await fireEvent.press(getByText("Select job titles"));
    await fireEvent.changeText(getByPlaceholderText("Search job titles"), "Prompt Designer");
    await fireEvent.press(getByText('my_job.role_add_custom:{"text":"Prompt Designer"}'));

    expect(baseProps.onChange).toHaveBeenCalledWith(["Prompt Designer"]);
  });

  it("stops adding at the max and says so", async () => {
    const { getByText, queryByText } = await render(
      <SearchableMultiSelect {...baseProps} values={["Chef", "Nurse", "Teacher"]} />,
    );

    expect(getByText('my_job.picker_max_reached:{"max":3}')).toBeTruthy();

    await fireEvent.press(getByText("Chef, Nurse, Teacher"));
    // List only offers unpicked options; adding is blocked at the cap.
    expect(queryByText("Sous Chef")).toBeTruthy();
    await fireEvent.press(getByText("Sous Chef"));
    expect(baseProps.onChange).not.toHaveBeenCalled();
  });

  it("removes a picked value from its chip", async () => {
    const { getByLabelText } = await render(
      <SearchableMultiSelect {...baseProps} values={["Chef", "Nurse"]} />,
    );

    await fireEvent.press(getByLabelText('my_job.role_remove_a11y:{"role":"Chef"}'));

    expect(baseProps.onChange).toHaveBeenCalledWith(["Nurse"]);
  });
});
