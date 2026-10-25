type PhoneClockModule = typeof import("@/lib/datetime/phoneClock");

type FakeLocalization = {
  getCalendars: jest.Mock;
  addListener: jest.Mock;
};

let mockLocalization: FakeLocalization | null = null;
jest.mock("expo-modules-core", () => ({
  requireOptionalNativeModule: (name: string) => (name === "ExpoLocalization" ? mockLocalization : null),
}));

/** A fresh copy: the module keeps the native module it found. */
function load(localization: FakeLocalization | null): PhoneClockModule {
  mockLocalization = localization;
  let loaded: PhoneClockModule | undefined;
  jest.isolateModules(() => {
    loaded = jest.requireActual<PhoneClockModule>("@/lib/datetime/phoneClock");
  });
  return loaded!;
}

function localization(uses24hourClock: boolean | null): FakeLocalization {
  return {
    getCalendars: jest.fn(() => [{ calendar: "gregory", timeZone: "Asia/Kathmandu", uses24hourClock, firstWeekday: 1 }]),
    addListener: jest.fn(() => ({ remove: jest.fn() })),
  };
}

describe("readPhoneClock", () => {
  it.each([
    [true, "h23"],
    [false, "h12"],
  ])("maps the phone's 24-Hour Time switch %s to %s", (uses24, hourCycle) => {
    expect(load(localization(uses24)).readPhoneClock().hourCycle).toBe(hourCycle);
  });

  it("reads the switch again on each read, so a change in Settings shows", () => {
    const native = localization(false);
    const { readPhoneClock } = load(native);
    expect(readPhoneClock().hourCycle).toBe("h12");
    native.getCalendars.mockReturnValue([{ uses24hourClock: true }]);
    expect(readPhoneClock().hourCycle).toBe("h23");
  });

  it.each([
    ["a build without the module", null],
    ["a module that cannot tell", localization(null)],
  ])("falls back to the phone locale's own clock for %s", (_label, native) => {
    const { localeUses24HourClock, readPhoneClock } = load(native);
    expect(readPhoneClock().hourCycle).toBe(localeUses24HourClock() ? "h23" : "h12");
  });

  it("falls back when the native call throws", () => {
    const native = localization(true);
    native.getCalendars.mockImplementation(() => {
      throw new Error("gone");
    });
    const { localeUses24HourClock, readPhoneClock } = load(native);
    expect(readPhoneClock().hourCycle).toBe(localeUses24HourClock() ? "h23" : "h12");
  });

  it("takes the zone from the engine, the one local Date fields use", () => {
    const { deviceTimeZone, readPhoneClock } = load(localization(true));
    expect(readPhoneClock().timeZone).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone);
    expect(deviceTimeZone()).toBe(readPhoneClock().timeZone);
  });
});

describe("localeUses24HourClock", () => {
  it.each([
    ["en-US", false],
    ["de-DE", true],
    ["fr-FR", true],
    ["ru-RU", true],
    ["en-GB", true],
  ])("%s uses a 24-hour clock: %s", (locale, expected) => {
    expect(load(null).localeUses24HourClock(locale)).toBe(expected);
  });
});

describe("onPhoneClockChange", () => {
  it("listens for the OS's calendar change and stops", () => {
    const native = localization(true);
    const remove = jest.fn();
    native.addListener.mockReturnValue({ remove });
    const listener = jest.fn();
    const stop = load(native).onPhoneClockChange(listener);
    expect(native.addListener).toHaveBeenCalledWith("onCalendarSettingsChanged", listener);
    stop();
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it("is a no-op in a build without the module", () => {
    expect(() => load(null).onPhoneClockChange(jest.fn())()).not.toThrow();
  });
});
