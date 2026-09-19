import { fireEvent, render, waitFor } from "@testing-library/react-native";

import {
  composePlace,
  EMPTY_PLACE,
  LocationFields,
  parsePlace,
} from "@/components/jobSearch/LocationFields";
import { requestDevicePlace } from "@/lib/deviceLocation";

jest.mock("@expo/vector-icons", () => ({
  Ionicons: "Ionicons",
}));

jest.mock("react-native-safe-area-context", () => ({
  useSafeAreaInsets: () => ({ top: 47, bottom: 34, left: 0, right: 0 }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/lib/reduceMotion", () => ({
  useReduceMotion: () => false,
}));

jest.mock("@/lib/deviceLocation", () => ({
  requestDevicePlace: jest.fn(),
}));

jest.mock("@shopify/flash-list", () => ({
  FlashList: ({
    data,
    renderItem,
  }: {
    data: string[];
    renderItem: (args: { item: string }) => React.ReactNode;
  }) => {
    const React = jest.requireActual<typeof import("react")>("react");
    return React.createElement(
      React.Fragment,
      null,
      ...data.map((item) =>
        React.createElement(React.Fragment, { key: item }, renderItem({ item })),
      ),
    );
  },
}));

const mockRequestDevicePlace = jest.mocked(requestDevicePlace);

describe("parsePlace / composePlace", () => {
  it("round-trips a full US location", () => {
    const place = parsePlace("Austin, Texas, United States");
    expect(place).toEqual({ country: "United States", region: "Texas", city: "Austin" });
    expect(composePlace(place)).toBe("Austin, Texas, United States");
  });

  it("snaps lowercase country/region to canonical names, keeps city as typed", () => {
    expect(parsePlace("toronto, ontario, canada")).toEqual({
      country: "Canada",
      region: "Ontario",
      city: "toronto",
    });
  });

  it("keeps unrecognized free text as the city so nothing is lost", () => {
    const place = parsePlace("Remote friendly, Addis Ababa");
    expect(place.country).toBe("");
    expect(place.city).toBe("Remote friendly, Addis Ababa");
  });

  it("handles empty input", () => {
    expect(parsePlace("")).toEqual(EMPTY_PLACE);
    expect(composePlace(EMPTY_PLACE)).toBe("");
  });
});

describe("LocationFields", () => {
  const baseProps = {
    value: EMPTY_PLACE,
    onChange: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("opens the country sheet and selects a country", async () => {
    const { getByText } = await render(<LocationFields {...baseProps} />);

    await fireEvent.press(getByText("my_job.location_country_placeholder"));
    await fireEvent.press(getByText("Ethiopia"));

    expect(baseProps.onChange).toHaveBeenCalledWith({
      country: "Ethiopia",
      region: "",
      city: "",
    });
  });

  it("shows a state dropdown for the US and clears region on country change", async () => {
    const us = { country: "United States", region: "Texas", city: "" };
    const { getByText } = await render(<LocationFields {...baseProps} value={us} />);

    // Region is a picker (not a text input) for the US.
    await fireEvent.press(getByText("Texas"));
    await fireEvent.press(getByText("California"));
    expect(baseProps.onChange).toHaveBeenCalledWith({ ...us, region: "California" });

    // Switching country clears the stale region.
    baseProps.onChange.mockClear();
    await fireEvent.press(getByText("United States"));
    await fireEvent.press(getByText("Germany"));
    expect(baseProps.onChange).toHaveBeenCalledWith({ country: "Germany", region: "", city: "" });
  });

  it("fills all fields from device GPS", async () => {
    mockRequestDevicePlace.mockResolvedValue({
      status: "granted",
      place: { city: "Addis Ababa", region: "Addis Ababa", country: "Ethiopia" },
    });
    const { getByText } = await render(<LocationFields {...baseProps} />);

    await fireEvent.press(getByText("settings.use_current_location"));

    await waitFor(() => {
      expect(baseProps.onChange).toHaveBeenCalledWith({
        country: "Ethiopia",
        region: "Addis Ababa",
        city: "Addis Ababa",
      });
    });
  });

  it("shows an inline hint when permission is denied", async () => {
    mockRequestDevicePlace.mockResolvedValue({ status: "denied" });
    const { getByText } = await render(<LocationFields {...baseProps} />);

    await fireEvent.press(getByText("settings.use_current_location"));

    await waitFor(() => {
      expect(getByText("my_job.location_denied")).toBeTruthy();
    });
    expect(baseProps.onChange).not.toHaveBeenCalled();
  });
});
