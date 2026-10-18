import { render } from "@testing-library/react-native";
import { PhysicsSolutionBlock } from "../PhysicsSolutionBlock";

const validPayload = {
  given: ["$m = 5\\text{ kg}$", "$v = 10\\text{ m/s}$"],
  find: "$E_k$",
  formula: ["Formula:", "$E_k = \\frac{1}{2}mv^2$"],
  assumptions: ["Assumption: Non-relativistic speed."],
  substitution: ["$E_k = \\frac{1}{2} \\cdot 5 \\cdot 10^2$"],
  answer: "250 J",
};

jest.mock("react-i18next", () => {
  const english = jest.requireActual("@/lib/i18n/en.json") as Record<
    string,
    string
  >;
  return {
    useTranslation: () => ({
      t: (key: string, options?: Record<string, unknown>) =>
        String(english[key] ?? key).replace(
          /\{\{(\w+)\}\}/g,
          (_, name: string) => String(options?.[name]),
        ),
    }),
  };
});

jest.mock("@/lib/theme", () => {
  const actual = jest.requireActual("@/lib/theme");
  return { ...actual, useTheme: () => actual.lightTheme };
});

jest.mock("@/ui/icons/Icon", () => ({ Icon: () => null }));

jest.mock("@/components/rich/CardShell", () => {
  const { View } = require("react-native");
  return {
    CardShell: ({ children }: any) => (
      <View testID="card-shell">{children}</View>
    ),
  };
});

describe("PhysicsSolutionBlock", () => {
  it("renders correctly with valid payload", async () => {
    const { getByText } = await render(
      <PhysicsSolutionBlock content={JSON.stringify(validPayload)} />,
    );

    expect(getByText("Given")).toBeTruthy();
    expect(getByText("$m = 5\\text{ kg}$")).toBeTruthy();
    expect(getByText("$v = 10\\text{ m/s}$")).toBeTruthy();

    expect(getByText("Find")).toBeTruthy();
    expect(getByText("$E_k$")).toBeTruthy();

    expect(getByText("Formula")).toBeTruthy();
    expect(getByText("$E_k = \\frac{1}{2}mv^2$")).toBeTruthy();

    expect(getByText("Assumption: Non-relativistic speed.")).toBeTruthy();

    expect(getByText("Substitution")).toBeTruthy();
    expect(getByText("$E_k = \\frac{1}{2} \\cdot 5 \\cdot 10^2$")).toBeTruthy();

    expect(getByText("Answer")).toBeTruthy();
    // RichBodyText strips "**" and outputs children as text.
    // The test environment might not fully support nested markdown, so we check using regex or exact text.
    expect(getByText("250 J")).toBeTruthy();
  });

  it("handles malformed JSON gracefully", async () => {
    const { queryByTestId } = await render(
      <PhysicsSolutionBlock content="bad json" />,
    );
    expect(queryByTestId("card-shell")).toBeNull();
  });
});
