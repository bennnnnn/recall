import { render } from "@testing-library/react-native";

import { ArrayBlock } from "@/components/rich/ArrayBlock";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: {
    t: (key: string, args?: { index?: number }) => (args ? `${key}:${args.index}` : key),
  },
}));

describe("ArrayBlock", () => {
  it("draws each value over its index", async () => {
    const view = await render(
      <ArrayBlock content='{"name":"nums","values":[2,7,11,15],"highlight":[0,1]}' />,
    );
    expect(view.getByText("nums")).toBeTruthy();
    expect(view.getByText("11")).toBeTruthy();
    expect(view.getByText("rich.array_index:3")).toBeTruthy();
    expect(view.getByLabelText("nums = [2, 7, 11, 15]")).toBeTruthy();
  });

  it("draws nothing while the list is still streaming in", async () => {
    const view = await render(<ArrayBlock content='{"values": [1, 2' />);
    expect(view.toJSON()).toBeNull();
  });

  it("says so instead of drawing a broken list", async () => {
    const view = await render(<ArrayBlock content='{"values": []}' />);
    expect(view.getByText("rich.array_error")).toBeTruthy();
  });
});
