import { fireEvent, render } from "@testing-library/react-native";

import { MapBlock } from "@/components/rich/MapBlock";

jest.mock("@/lib/i18n", () => ({
  __esModule: true,
  default: {
    t: (key: string, args?: { place?: string }) => (args?.place ? `${key}:${args.place}` : key),
  },
}));

describe("MapBlock", () => {
  it("names the place and its country, and draws once it has a width", async () => {
    const view = await render(
      <MapBlock content='{"place":"Nairobi","lat":-1.29,"lon":36.82,"zoom":"city"}' />,
    );
    expect(view.getByText("Nairobi")).toBeTruthy();
    expect(view.getByText("Kenya · 1.29° S, 36.82° E")).toBeTruthy();
    const map = view.getByLabelText("rich.map_a11y:Nairobi");
    await fireEvent(map, "layout", { nativeEvent: { layout: { width: 320, height: 160 } } });
    expect(view.toJSON()).toBeTruthy();
  });

  it("leaves out the country when the place is the country", async () => {
    const view = await render(<MapBlock content='{"place":"Kenya","lat":0.02,"lon":37.91}' />);
    expect(view.getByText("0.02° N, 37.91° E")).toBeTruthy();
  });

  it("says so instead of drawing a broken map", async () => {
    const view = await render(<MapBlock content="{not json" />);
    expect(view.getByText("rich.map_error")).toBeTruthy();
  });
});
